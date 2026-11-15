"""Backend del tablero: API + página web en un solo servidor.

Arranque (desde la carpeta del proyecto):
    python backend/app.py
y abre  http://127.0.0.1:8000

Endpoints:
    GET  /api/salud                     estado: base, modelos, número de fragmentos
    GET  /api/experimentos              los 24 experimentos (para tarjetas y filtros)
    GET  /api/pruebas?experimento_id=…  pruebas limpias (números exactos salen de aquí, no del chat)
    POST /api/chat                      pregunta -> RAG (fragmentos) -> Gemini o Groq -> respuesta con fuentes
                                        (modo "bitacora": analiza sólo la bitácora que manda la página)
                                        (+ escenarios_propuestos: casos que la IA sugiere probar en el simulador)
    GET  /docs                          documentación automática para probar la API

Usa lo mismo que los scripts: DATABASE_URL, MODELO_EMBEDDINGS, MODELO_CHAT, NIVEL_RAZONAMIENTO
y la clave del proveedor (GEMINI_API_KEY o GROQ_API_KEY) de .env. Las claves se quedan en el
servidor; la página nunca las ve.

Requiere:  pip install -r requirements.txt   (fastapi y uvicorn)
"""

from __future__ import annotations

import re
import sys
import threading
import time
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ImportError:
    raise SystemExit("Faltan fastapi/uvicorn. Instálalos con:  pip install -r requirements.txt")

import bd  # noqa: E402
from buscar import buscar, buscar_por_pilares, con_vecinos, preparar  # noqa: E402
from fuentes_generales import nombre_fuente  # noqa: E402
from gemini import ErrorIA  # noqa: E402
from seguridad import revisar_pregunta  # noqa: E402
from idioma import detectar_idioma  # noqa: E402
from llm import agrupar_fuentes, es_negativa, seguridad_al_reves, fuentes_citadas, quitar_veredictos, modelo_configurado, numeros_sin_respaldo, proveedor_de, responder  # noqa: E402
from llm import ids_sin_respaldo, responder_bitacora, unidades_sin_respaldo  # noqa: E402

FRONTEND = RAIZ / "frontend"


class Base:
    """Una sola conexión a Postgres compartida, protegida con un candado (pg8000 no es
    seguro entre hilos). Si la conexión se cae (Supabase cierra las inactivas), se reabre."""

    def __init__(self):
        self.candado = threading.Lock()
        self.conexion = None
        self.vectorizador = None

    def _abrir(self):
        try:
            self.conexion = bd.conectar()
        except SystemExit as e:  # bd.conectar() termina con mensajes claros: aquí los convertimos
            raise HTTPException(503, f"No hay conexión con la base de datos: {e}")
        # Ninguna consulta espera más de 5 s por una tabla ocupada (por ejemplo, mientras Cloud Run
        # cambia de versión): falla, se reintenta y el servidor nunca se queda colgado.
        try:
            cursor = self.conexion.cursor()
            cursor.execute("SET lock_timeout = '5s'")
            self.conexion.commit()
        except Exception:
            pass

    def ejecutar(self, funcion):
        """Corre funcion(conexion) con el candado; reintenta una vez reconectando."""
        with self.candado:
            for intento in (1, 2):
                if self.conexion is None:
                    self._abrir()
                try:
                    resultado = funcion(self.conexion)
                    self._terminar("commit")   # cierra la transacción: no deja la tabla ocupada entre peticiones
                    return resultado
                except (HTTPException, ErrorIA):
                    self._terminar("rollback")
                    raise
                except Exception:
                    try:
                        self.conexion.close()
                    except Exception:
                        pass
                    self.conexion = None
                    if intento == 2:
                        raise

    def _terminar(self, como: str):
        try:
            getattr(self.conexion, como)()
        except Exception:
            pass

    def vectorizador_listo(self, conexion):
        if self.vectorizador is None:
            try:
                self.vectorizador = preparar(conexion)
            except SystemExit as e:
                raise HTTPException(503, str(e))
        return self.vectorizador


base = Base()
app = FastAPI(title="Flame in Freefall API", version="0.1")
# Permite abrir la página desde otro lado (Live Server, archivo local) durante el desarrollo.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


def filas_a_dict(cursor) -> list[dict]:
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


# ---------------------------------------------------------------- API

def modelos_disponibles(env: dict) -> list[str]:
    """Modelos de chat que la página puede ofrecer, según las claves configuradas."""
    def hay(nombre):
        valor = (env.get(nombre) or "").strip()
        return bool(valor) and not valor.startswith("TU-")
    modelos = []
    if hay("GROQ_API_KEY"):
        modelos += ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    if hay("GEMINI_API_KEY"):
        modelos += ["gemini-flash-lite-latest"]
    return modelos


@app.get("/api/salud")
def salud():
    def consulta(conexion):
        cursor = conexion.cursor()
        cursor.execute("SELECT count(*) FROM experimentos")
        experimentos = cursor.fetchone()[0]
        from embeddings import nombre_configurado, tabla_fragmentos
        tabla = base.vectorizador.tabla if base.vectorizador else tabla_fragmentos(nombre_configurado())
        cursor.execute(f"SELECT to_regclass('public.{tabla}') IS NOT NULL")
        fragmentos, modelos = 0, []
        if cursor.fetchone()[0]:
            cursor.execute(f"SELECT modelo_embedding, count(*) FROM {tabla} GROUP BY 1")
            filas = cursor.fetchall()
            modelos = [f[0] for f in filas]
            fragmentos = sum(f[1] for f in filas)
        return experimentos, fragmentos, modelos

    experimentos, fragmentos, modelos = base.ejecutar(consulta)
    env = bd.leer_env()
    modelo = modelo_configurado()
    proveedor = proveedor_de(modelo)
    clave = env.get("GROQ_API_KEY" if proveedor == "groq" else "GEMINI_API_KEY", "").strip()
    return {
        "ok": True,
        "experimentos": experimentos,
        "fragmentos": fragmentos,
        "modelo_embeddings": modelos[0] if len(modelos) == 1 else modelos,
        "modelo_chat": modelo,
        "proveedor_chat": proveedor,
        "ia_configurada": bool(clave and not clave.startswith("TU-")),
        "modelos_chat": modelos_disponibles(env),
        "falta_clave": "" if clave and not clave.startswith("TU-") else
                       ("GROQ_API_KEY" if proveedor == "groq" else "GEMINI_API_KEY"),
    }


@app.get("/api/experimentos")
def experimentos():
    def consulta(conexion):
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT e.id, e.acronimo, e.titulo, e.tipo, e.pilar, e.tipo_combustible, e.familia_equipo, "
            "e.resumen_es, e.plataforma, e.fecha_inicio, e.fecha_fin, e.doi, e.url, "
            "(SELECT count(*) FROM pruebas p WHERE p.experimento_id = e.id) AS pruebas "
            "FROM experimentos e ORDER BY e.tipo, e.acronimo")
        return filas_a_dict(cursor)
    return base.ejecutar(consulta)


@app.get("/api/pruebas")
def pruebas(experimento_id: str = "", resultado: str = "", limite: int = 200):
    limite = max(1, min(limite, 2000))

    def consulta(conexion):
        filtros, parametros = [], []
        if experimento_id:
            filtros.append("experimento_id = %s")
            parametros.append(experimento_id)
        if resultado:
            filtros.append("resultado = %s")
            parametros.append(resultado)
        donde = f"WHERE {' AND '.join(filtros)}" if filtros else ""
        cursor = conexion.cursor()
        cursor.execute(f"SELECT * FROM pruebas {donde} ORDER BY id LIMIT %s", parametros + [limite])
        return filas_a_dict(cursor)
    return base.ejecutar(consulta)


# --- Órbita de la Estación Espacial Internacional (para el visor 3D en 0 g) ---
# Se bajan sus elementos orbitales (TLE) de CelesTrak y la página calcula la posición con SGP4.
# Se guardan 2 horas para no consultar de más; si no hay internet se reusan los últimos.
ISS_TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE"
_iss = {"hora": 0.0, "datos": None}
_iss_candado = threading.Lock()


@app.get("/api/iss")
def iss():
    import os
    import urllib.request
    from datetime import datetime, timezone

    with _iss_candado:
        if _iss["datos"] and time.time() - _iss["hora"] < 2 * 3600:
            return _iss["datos"]
        url = os.environ.get("ISS_TLE_URL", ISS_TLE_URL)
        try:
            pedido = urllib.request.Request(url, headers={"User-Agent": "FlameInFreefall/1.0 (NASA Space Apps)"})
            with urllib.request.urlopen(pedido, timeout=8) as r:
                lineas = [l.strip() for l in r.read().decode("utf-8", "replace").splitlines() if l.strip()]
            l1 = next(l for l in lineas if l.startswith("1 "))
            l2 = next(l for l in lineas if l.startswith("2 "))
            nombre = lineas[0] if not lineas[0].startswith("1 ") else "ISS (ZARYA)"
            _iss["datos"] = {"nombre": nombre, "tle1": l1, "tle2": l2, "fuente": "CelesTrak",
                             "obtenido": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            _iss["hora"] = time.time()
            return _iss["datos"]
        except Exception as e:  # sin internet o respuesta rara
            if _iss["datos"]:
                return {**_iss["datos"], "desactualizado": True}
            raise HTTPException(503, f"No se pudo obtener la órbita de la EEI: {e}")


class Pregunta(BaseModel):
    pregunta: str = Field(..., min_length=2, max_length=1500)
    k: int = Field(8, ge=1, le=20, description="fragmentos a buscar")
    experimento_id: str = ""
    pilar: str = ""
    contexto: str = Field("", max_length=6000, description="datos actuales del tablero (no son fuente); "
                                                       "en modo bitacora, la bitácora completa")
    estilo: str = Field("", description="engineer | student")
    modelo: str = Field("", description="modelo de chat, ej. openai/gpt-oss-120b (vacío = MODELO_CHAT de .env)")
    vecinos: bool = True
    hibrida: bool = Field(True, description="búsqueda por significado + palabras clave")
    diversa: bool = Field(True, description="máx. 2 fragmentos por documento y 4 por experimento")
    por_pilar: bool = Field(False, description="una búsqueda por pilar y respuesta en 3 viñetas (dictamen)")
    dictamen: Optional[bool] = Field(None, description="true = dictamen del escenario (botón Interpretar); "
                                     "false = pregunta libre con los datos actuales del tablero en `contexto`; "
                                     "vacío = se deduce como antes (por_pilar y contexto)")
    modo: str = Field("", pattern=r"^(bitacora)?$",
                      description="bitacora = analizar la bitácora de pruebas que viene en `contexto` usando SÓLO "
                                  "esa bitácora (sin buscar en los documentos); vacío = chat normal")
    idioma: str = Field("", pattern=r"^(es|en)?$",
                        description="idioma de la página (es | en). La IA responde en el idioma de la pregunta; "
                                    "si no se distingue, en este")


@app.post("/api/chat")
def chat(p: Pregunta):
    if p.modelo and (".." in p.modelo or not re.fullmatch(r"[a-z0-9][a-z0-9._\-]*(/[a-z0-9._\-]+)?", p.modelo)):
        raise HTTPException(400, "Nombre de modelo no válido.")
    inicio = time.time()
    # Idioma de la respuesta: el de la pregunta (o el que pida explícitamente); si no se nota, el de la página
    idioma = detectar_idioma(p.pregunta, p.idioma or "es")
    bloqueo = revisar_pregunta(p.pregunta, idioma)
    if bloqueo:  # filtro de seguridad: respuesta fija, sin buscar ni llamar a la IA
        return {"respuesta": bloqueo[1], "fuentes": [], "cifras_sin_respaldo": [], "fragmentos_usados": 0,
                "modelo": "safety filter" if idioma == "en" else "filtro de seguridad", "bloqueada": bloqueo[0],
                "escenarios_propuestos": [], "idioma": idioma, "segundos": round(time.time() - inicio, 1)}

    if p.modo == "bitacora":
        return chat_bitacora(p, idioma, inicio)

    def recuperar(conexion):
        vectorizador = base.vectorizador_listo(conexion)
        if p.por_pilar:
            fragmentos = buscar_por_pilares(conexion, vectorizador, p.pregunta, max(p.k, 9))
        else:
            fragmentos = buscar(conexion, vectorizador, p.pregunta, p.k, p.experimento_id, p.pilar,
                                hibrida=p.hibrida, diversa=p.diversa)
        return con_vecinos(conexion, fragmentos, tabla=vectorizador.tabla) if p.vecinos else fragmentos

    escenarios: list[dict] = []  # escenarios que la IA propone probar en el simulador (escenarios.py)
    try:
        fragmentos = base.ejecutar(recuperar)
        # La IA va fuera del candado: puede tardar y no debe bloquear otras consultas.
        texto = responder(p.pregunta, fragmentos, p.modelo or None, p.contexto, p.estilo,
                          por_pilar=p.por_pilar, idioma=idioma, escenarios=escenarios, dictamen=p.dictamen)
    except ErrorIA as e:
        raise HTTPException(502, f"La IA no pudo responder: {str(e).splitlines()[0]}")
    texto, quitadas = quitar_veredictos(texto, f"{p.pregunta} {p.contexto}", idioma)

    fuentes = [{
        "n": numeros[0],
        "numeros": numeros,
        "experimento": nombre_fuente(f),
        "general": bool(f.get("fuente_general")),
        "pilar": f.get("pilar"),
        "experimento_id": f["experimento_id"],
        "documento": f.get("titulo_documento") or Path(f["archivo"]).name,
        "tipo_documento": f.get("tipo_documento"),
        "pagina": f.get("pagina"),
        "doi": f.get("doi"),
        "url": f"https://doi.org/{f['doi']}" if f.get("doi") else None,
        "similitud": round(float(f["similitud"]), 3),
        "via": f.get("via"),
    } for numeros, f in agrupar_fuentes(fuentes_citadas(texto, fragmentos))]
    return {
        "respuesta": texto,
        "fuentes": fuentes,
        # Cifras de la respuesta que no aparecen en los fragmentos: la página las marca.
        "cifras_sin_respaldo": numeros_sin_respaldo(texto, fragmentos, f"{p.pregunta} {p.contexto}"),
        "fragmentos_usados": len(fragmentos),
        "modelo": modelo_configurado(p.modelo or None),
        "bloqueada": "",
        "veredictos_quitados": quitadas,
        "seguridad_al_reves": seguridad_al_reves(texto),
        "negativa": es_negativa(texto),
        # Campo nuevo (opcional para quien consuma la API): escenarios para el botón "Aplicar al simulador".
        # Valores en % de O2, psi, fracción de g y cm/s; None = ese parámetro no cambia.
        "escenarios_propuestos": [] if es_negativa(texto) else escenarios,
        "idioma": idioma,
        "segundos": round(time.time() - inicio, 1),
    }


def chat_bitacora(p: Pregunta, idioma: str, inicio: float) -> dict:
    """Análisis de una bitácora de pruebas: la IA sólo ve la bitácora (sin fragmentos ni base de datos).
    Se revisa que no use cifras ni pruebas que no estén en la bitácora."""
    if not p.contexto.strip():
        raise HTTPException(400, "Falta la bitácora en `contexto`.")
    try:
        texto = responder_bitacora(p.pregunta, p.contexto, p.modelo or None, p.estilo, idioma)
    except ErrorIA as e:
        raise HTTPException(502, f"La IA no pudo responder: {str(e).splitlines()[0]}")
    return {
        "respuesta": texto,
        "fuentes": [],
        # Cifras e identificadores de prueba que no aparecen en la bitácora: la página los marca.
        "cifras_sin_respaldo": numeros_sin_respaldo(texto, [], f"{p.pregunta} {p.contexto}"),
        "ids_sin_respaldo": ids_sin_respaldo(texto, f"{p.pregunta} {p.contexto}"),
        "unidades_sin_respaldo": unidades_sin_respaldo(texto, f"{p.pregunta} {p.contexto}"),
        "fragmentos_usados": 0,
        "modelo": modelo_configurado(p.modelo or None),
        "bloqueada": "",
        "veredictos_quitados": [],
        "seguridad_al_reves": seguridad_al_reves(texto),
        "negativa": es_negativa(texto),
        "escenarios_propuestos": [],
        "modo": "bitacora",
        "idioma": idioma,
        "segundos": round(time.time() - inicio, 1),
    }


# ---------------------------------------------------------------- página web

@app.get("/", include_in_schema=False)
def inicio():
    pagina = FRONTEND / "index.html"
    if not pagina.exists():
        raise HTTPException(404, "No existe frontend/index.html")
    return FileResponse(pagina)


if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")


if __name__ == "__main__":
    import argparse

    import uvicorn

    p = argparse.ArgumentParser(description="Servidor del tablero (API + página).")
    p.add_argument("--puerto", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1", help="usa 0.0.0.0 para que lo vean otras compus de tu red")
    args = p.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("Conectando a la base y preparando el modelo de búsqueda (la primera vez tarda)...")
    try:
        base.ejecutar(base.vectorizador_listo)
    except Exception as e:  # el servidor arranca igual: /api/salud dirá qué falta y se reintenta en cada petición
        detalle = getattr(e, "detail", None) or f"{type(e).__name__}: {e}"
        print(f"\nAVISO: no pude preparar la base o el modelo al arrancar: {detalle}\n"
              "El servidor arranca igual y lo vuelve a intentar con la primera pregunta.", flush=True)
    print(f"\nListo. Abre en tu navegador:  http://127.0.0.1:{args.puerto}")
    print(f"Documentación de la API:      http://127.0.0.1:{args.puerto}/docs")
    print("Para detenerlo: Ctrl+C\n")
    uvicorn.run(app, host=args.host, port=args.puerto, log_level="warning")
