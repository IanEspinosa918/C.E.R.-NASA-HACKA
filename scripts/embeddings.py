"""Convierte texto en vectores (embeddings) para el chat con RAG.

Usa un modelo LOCAL y gratuito (fastembed): corre en tu computadora, sin claves ni costo.
La primera vez descarga el modelo (~220 MB) y lo guarda para las siguientes.

Modelo por defecto: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
  - 384 dimensiones
  - multilingüe: una pregunta en español encuentra documentos en inglés
  - sólo lee ~128 tokens por texto (unos 500 caracteres): por eso los fragmentos son cortos

IMPORTANTE: las preguntas del chat deben vectorizarse con EXACTAMENTE el mismo modelo
que los documentos. El backend debe usar esta misma clase (o el mismo modelo).

Requiere:  pip install fastembed
"""

from __future__ import annotations

import hashlib
import math
import re

MODELO_POR_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODELO_DE_PRUEBA = "prueba"  # vectores falsos para probar la tubería sin descargar nada


class Vectorizador:
    def __init__(self, nombre: str = MODELO_POR_DEFECTO):
        self.nombre = nombre or MODELO_POR_DEFECTO
        self._modelo = None
        if self.nombre == MODELO_DE_PRUEBA:
            self.dimension = 384
            return
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise SystemExit("Falta fastembed. Instálalo con:  pip install -r requirements.txt")
        print(f"Cargando el modelo de embeddings '{self.nombre}' "
              "(la primera vez se descarga; puede tardar unos minutos)...")
        try:
            self._modelo = TextEmbedding(model_name=self.nombre)
        except Exception as e:
            raise SystemExit(f"No pude cargar el modelo '{self.nombre}': {e}\n"
                             "Revisa tu conexión a internet y el nombre del modelo (MODELO_EMBEDDINGS en .env).")
        self.dimension = len(self._vectores(["prueba"])[0])

    # Los modelos E5 necesitan un prefijo distinto para documentos y para preguntas.
    def _prefijo(self, tipo: str) -> str:
        return ("passage: " if tipo == "documento" else "query: ") if "e5" in self.nombre.lower() else ""

    def _vectores(self, textos: list[str]) -> list[list[float]]:
        if self._modelo is None:
            return [_vector_de_prueba(t, self.dimension) for t in textos]
        return [[float(x) for x in v] for v in self._modelo.embed(textos, batch_size=32)]

    def documentos(self, textos: list[str]) -> list[list[float]]:
        return self._vectores([self._prefijo("documento") + t for t in textos])

    def pregunta(self, texto: str) -> list[float]:
        return self._vectores([self._prefijo("pregunta") + texto])[0]


def a_pgvector(vector: list[float]) -> str:
    """Formato de texto que entiende pgvector: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def _vector_de_prueba(texto: str, dimension: int) -> list[float]:
    """Vector falso por conteo de palabras. Sólo coincide por palabras idénticas:
    NO entiende significado ni cruza español-inglés. No usar para el chat real."""
    v = [0.0] * dimension
    for palabra in re.findall(r"[a-záéíóúñü0-9]{3,}", texto.lower()):
        v[int(hashlib.md5(palabra.encode()).hexdigest(), 16) % dimension] += 1.0
    norma = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norma for x in v]
