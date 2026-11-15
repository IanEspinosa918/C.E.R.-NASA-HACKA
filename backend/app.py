"""Backend del tablero: API + página web en un solo servidor.

Arranque (desde la carpeta del proyecto):
    python backend/app.py
y abre  http://127.0.0.1:8000

Endpoints:
    GET  /api/salud                     estado: base, modelos, número de fragmentos
    GET  /api/experimentos              los 24 experimentos (para tarjetas y filtros)
    GET  /api/pruebas?experimento_id=…  pruebas limpias (números exactos salen de aquí, no del chat)
    POST /api/chat                      pregunta -> RAG (fragmentos) -> Gemini -> respuesta con fuentes
    GET  /docs                          documentación automática para probar la API

Usa lo mismo que los scripts: DATABASE_URL, MODELO_EMBEDDINGS, GEMINI_API_KEY, MODELO_CHAT
y NIVEL_RAZONAMIENTO de .env. La clave de Gemini se queda en el servidor; la página nunca la ve.

Requiere:  pip install -r requirements.txt   (fastapi y uvicorn)
"""

from __future__ import annotations

import re
import sys
import threading
import time
from pathlib import Path

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
from buscar import buscar, con_vecinos, preparar  # noqa: E402
from gemini import ErrorGemini  # noqa: E402
from llm import MODELO_CHAT_POR_DEFECTO, fuentes_citadas, responder  # noqa: E402

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

    def ejecutar(self, funcion):
        """Corre funcion(conexion) con el candado; reintenta una vez reconectando."""
        with self.candado:
            for intento in (1, 2):
                if self.conexion is None:
                    self._abrir()
                try:
                    return funcion(self.conexion)
                except (HTTPException, ErrorGemini):
                    raise
                except Exception:
                    try:
                        self.conexion.close()
                    except Exception:
                        pass
                    self.conexion = None
                    if intento == 2:
                        raise

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

@app.get("/api/salud")
def salud():
    def consulta(conexion):
        cursor = conexion.cursor()
        cursor.execute("SELECT count(*) FROM experimentos")
        experimentos = cursor.fetchone()[0]
        cursor.execute("SELECT to_regclass('public.fragmentos') IS NOT NULL")
        fragmentos, modelos = 0, []
        if cursor.fetchone()[0]:
            cursor.execute("SELECT modelo_embedding, count(*) FROM fragmentos GROUP BY 1")
            filas = cursor.fetchall()
            modelos = [f[0] for f in filas]
            fragmentos = sum(f[1] for f in filas)
        return experimentos, fragmentos, modelos

    experimentos, fragmentos, modelos = base.ejecutar(consulta)
    env = bd.leer_env()
    return {
        "ok": True,
        "experimentos": experimentos,
        "fragmentos": fragmentos,
        "modelo_embeddings": modelos[0] if len(modelos) == 1 else modelos,
        "modelo_chat": env.get("MODELO_CHAT") or MODELO_CHAT_POR_DEFECTO,
        "gemini_configurado": bool(env.get("GEMINI_API_KEY", "").strip()
                                   and not env.get("GEMINI_API_KEY", "").startswith("TU-")),
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


class Pregunta(BaseModel):
    pregunta: str = Field(..., min_length=2, max_length=1500)
    k: int = Field(8, ge=1, le=20, description="fragmentos a buscar")
    experimento_id: str = ""
    pilar: str = ""
    contexto: str = Field("", max_length=3000, description="escenario del tablero (no es fuente)")
    estilo: str = Field("", description="engineer | student")
    modelo: str = Field("", description="modelo de chat (vacío = MODELO_CHAT de .env)")
    vecinos: bool = True


@app.post("/api/chat")
def chat(p: Pregunta):
    if p.modelo and not re.fullmatch(r"gemini[a-z0-9.\-]*", p.modelo):
        raise HTTPException(400, "Nombre de modelo no válido.")
    inicio = time.time()

    def recuperar(conexion):
        vectorizador = base.vectorizador_listo(conexion)
        fragmentos = buscar(conexion, vectorizador, p.pregunta, p.k, p.experimento_id, p.pilar)
        return con_vecinos(conexion, fragmentos) if p.vecinos else fragmentos

    try:
        fragmentos = base.ejecutar(recuperar)
        # Gemini fuera del candado: puede tardar y no debe bloquear otras consultas.
        texto = responder(p.pregunta, fragmentos, p.modelo or None, p.contexto, p.estilo)
    except ErrorGemini as e:
        raise HTTPException(502, f"Gemini no pudo responder: {str(e).splitlines()[0]}")

    fuentes = [{
        "n": n,
        "experimento": f["experimento"],
        "experimento_id": f["experimento_id"],
        "documento": f.get("titulo_documento") or Path(f["archivo"]).name,
        "tipo_documento": f.get("tipo_documento"),
        "pagina": f.get("pagina"),
        "doi": f.get("doi"),
        "url": f"https://doi.org/{f['doi']}" if f.get("doi") else None,
        "similitud": round(float(f["similitud"]), 3),
    } for n, f in fuentes_citadas(texto, fragmentos)]
    return {
        "respuesta": texto,
        "fuentes": fuentes,
        "fragmentos_usados": len(fragmentos),
        "modelo": p.modelo or bd.leer_env().get("MODELO_CHAT") or MODELO_CHAT_POR_DEFECTO,
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
    except HTTPException as e:
        raise SystemExit(f"\nNo pude arrancar: {e.detail}")
    print(f"\nListo. Abre en tu navegador:  http://127.0.0.1:{args.puerto}")
    print(f"Documentación de la API:      http://127.0.0.1:{args.puerto}/docs")
    print("Para detenerlo: Ctrl+C\n")
    uvicorn.run(app, host=args.host, port=args.puerto, log_level="warning")
