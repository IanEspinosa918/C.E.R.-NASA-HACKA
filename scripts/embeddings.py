"""Convierte texto en vectores (embeddings) para el chat con RAG.

Dos opciones, según MODELO_EMBEDDINGS en .env:

1. LOCAL (por defecto, gratis, sin claves): cualquier modelo de fastembed.
   MODELO_EMBEDDINGS=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
   La primera vez descarga el modelo (~220 MB). Lee ~128 tokens por texto.

2. GEMINI (API de Google, necesita GEMINI_API_KEY en .env):
   MODELO_EMBEDDINGS=gemini-embedding-001
   DIMENSIONES_EMBEDDINGS=768     (768, 1536 o 3072; con pgvector conviene 768 o 1536)
   Multilingüe, más preciso, lee hasta ~2048 tokens por texto. Tiene límites de uso.

IMPORTANTE: las preguntas del chat deben vectorizarse con EXACTAMENTE el mismo modelo
(y las mismas dimensiones) que los documentos. Si cambias de modelo hay que recargar:
    python scripts/cargar_fragmentos.py --recrear

Requiere:  pip install fastembed   (sólo para la opción local)
"""

from __future__ import annotations

import hashlib
import math
import re
import time

MODELO_POR_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODELO_DE_PRUEBA = "prueba"  # vectores falsos para probar la tubería sin descargar nada
LOTE_GEMINI = 100            # textos por solicitud a Gemini
PAUSA_GEMINI = 0.7           # segundos entre solicitudes (para no pasar el límite por minuto)


def es_gemini(nombre: str) -> bool:
    return nombre.lower().replace("models/", "").startswith("gemini")


class Vectorizador:
    """Uso:  v = Vectorizador(nombre);  v.documentos([...]);  v.pregunta("...")
    `v.nombre` es el identificador que se guarda en la base (incluye las dimensiones en Gemini)."""

    def __init__(self, nombre: str = MODELO_POR_DEFECTO, dimensiones: int | None = None):
        nombre = (nombre or MODELO_POR_DEFECTO).strip()
        self._modelo = None
        self._gemini = es_gemini(nombre)

        if nombre == MODELO_DE_PRUEBA:
            self.nombre, self.dimension = nombre, 384
            return

        if self._gemini:
            from bd import leer_env
            self._id_gemini = nombre.replace("models/", "").split("@")[0]
            if "@" in nombre and not dimensiones:
                dimensiones = int(nombre.split("@")[1])
            dimensiones = dimensiones or int(leer_env().get("DIMENSIONES_EMBEDDINGS") or 768)
            if not 128 <= dimensiones <= 3072:
                raise SystemExit("DIMENSIONES_EMBEDDINGS debe estar entre 128 y 3072 (recomendado: 768).")
            if dimensiones > 2000:
                print("AVISO: pgvector no puede crear el índice rápido (HNSW) con más de 2000 dimensiones; "
                      "usa 768 o 1536.")
            self.dimension = dimensiones
            self.nombre = f"{self._id_gemini}@{dimensiones}"
            return

        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise SystemExit("Falta fastembed. Instálalo con:  pip install -r requirements.txt")
        print(f"Cargando el modelo de embeddings '{nombre}' "
              "(la primera vez se descarga; puede tardar unos minutos)...")
        try:
            self._modelo = TextEmbedding(model_name=nombre)
        except Exception as e:
            raise SystemExit(f"No pude cargar el modelo '{nombre}': {e}\n"
                             "Revisa tu conexión a internet y el nombre del modelo (MODELO_EMBEDDINGS en .env).")
        self.nombre = nombre
        self.dimension = len(self._locales(["prueba"])[0])
        print("Modelo cargado.")

    @property
    def tabla(self) -> str:
        """Tabla de Postgres con los fragmentos vectorizados con este modelo."""
        return tabla_fragmentos(self.nombre)

    # ------------------------------------------------------------ local

    def _prefijo(self, tipo: str) -> str:
        # Los modelos E5 necesitan un prefijo distinto para documentos y para preguntas.
        return ("passage: " if tipo == "documento" else "query: ") if "e5" in self.nombre.lower() else ""

    def _locales(self, textos: list[str]) -> list[list[float]]:
        if self._modelo is None:
            return [_vector_de_prueba(t, self.dimension) for t in textos]
        return [[float(x) for x in v] for v in self._modelo.embed(textos, batch_size=32)]

    # ------------------------------------------------------------ Gemini

    def _gemini_vectores(self, textos: list[str], tipo_tarea: str) -> list[list[float]]:
        from gemini import llamar
        modelo = f"models/{self._id_gemini}"
        vectores = []
        for i in range(0, len(textos), LOTE_GEMINI):
            grupo = textos[i:i + LOTE_GEMINI]
            cuerpo = {"requests": [{
                "model": modelo,
                "content": {"parts": [{"text": t}]},
                # Campos "de primer nivel": en la API real, embedContentConfig dentro de un
                # lote se ignora (regresa 3072 dimensiones). Estos sí los respeta.
                "taskType": tipo_tarea,
                "outputDimensionality": self.dimension,
            } for t in grupo]}
            respuesta = llamar(f"{modelo}:batchEmbedContents", cuerpo)
            recibidos = [e.get("values") or [] for e in respuesta.get("embeddings", [])]
            # Si aun así llegan más dimensiones, se recortan: el modelo está entrenado (MRL) para
            # que los primeros N valores sigan siendo un buen vector; luego se normaliza.
            recibidos = [v[: self.dimension] for v in recibidos]
            if len(recibidos) != len(grupo) or any(len(v) != self.dimension for v in recibidos):
                raise SystemExit(f"Gemini regresó {len(recibidos)} vectores para {len(grupo)} textos "
                                 f"(o de tamaño distinto a {self.dimension}). Respuesta inesperada.")
            vectores.extend(_normalizar(v) for v in recibidos)  # obligatorio si no son 3072 dims
            if i + LOTE_GEMINI < len(textos):
                time.sleep(PAUSA_GEMINI)
        return vectores

    # ------------------------------------------------------------ uso

    def documentos(self, textos: list[str]) -> list[list[float]]:
        if self._gemini:
            return self._gemini_vectores(textos, "RETRIEVAL_DOCUMENT")
        return self._locales([self._prefijo("documento") + t for t in textos])

    def pregunta(self, texto: str) -> list[float]:
        if self._gemini:
            return self._gemini_vectores([texto], "RETRIEVAL_QUERY")[0]
        return self._locales([self._prefijo("pregunta") + texto])[0]


def tabla_fragmentos(nombre_modelo: str) -> str:
    """Tabla donde viven los vectores de ese modelo. Cada modelo tiene la suya para poder
    probar uno nuevo (por ejemplo Gemini) sin borrar el que ya funciona:
      modelo local (MiniLM, etc.) -> fragmentos
      Gemini                      -> fragmentos_gemini
    TABLA_FRAGMENTOS en .env la fija a mano (sólo letras, números y _)."""
    from bd import leer_env
    fija = (leer_env().get("TABLA_FRAGMENTOS") or "").strip()
    if fija:
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,40}", fija):
            raise SystemExit("TABLA_FRAGMENTOS sólo puede tener minúsculas, números y _.")
        return fija
    return "fragmentos_gemini" if es_gemini(nombre_modelo) else "fragmentos"


def nombre_configurado(argumento: str | None = None) -> str:
    """Modelo a usar: el del argumento, si no el de .env, si no el de por defecto."""
    from bd import leer_env
    return argumento or leer_env().get("MODELO_EMBEDDINGS") or MODELO_POR_DEFECTO


def a_pgvector(vector: list[float]) -> str:
    """Formato de texto que entiende pgvector: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def _normalizar(vector: list[float]) -> list[float]:
    norma = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [float(x) / norma for x in vector]


def _vector_de_prueba(texto: str, dimension: int) -> list[float]:
    """Vector falso por conteo de palabras. Sólo coincide por palabras idénticas:
    NO entiende significado ni cruza español-inglés. No usar para el chat real."""
    v = [0.0] * dimension
    for palabra in re.findall(r"[a-záéíóúñü0-9]{3,}", texto.lower()):
        v[int(hashlib.md5(palabra.encode()).hexdigest(), 16) % dimension] += 1.0
    return _normalizar(v)
