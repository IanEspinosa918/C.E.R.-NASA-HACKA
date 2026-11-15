"""Conexión a Postgres compartida por cargar_bd.py, cargar_fragmentos.py y buscar.py.

La dirección de la base se lee de la variable DATABASE_URL, que va en el archivo .env
de la raíz del proyecto (copia .env.example a .env y pon ahí tu dirección).
El archivo .env NO se sube a GitHub.

Funciona con cualquier Postgres 15+ con la extensión pgvector: Supabase, Neon o local.
Requiere:  pip install pg8000
"""

from __future__ import annotations

import os
import re
import ssl
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_ENV = RAIZ / ".env"
ESQUEMA = RAIZ / "backend" / "esquema.sql"


def leer_env() -> dict:
    """Lee .env (KEY=valor por línea). Las variables del sistema tienen prioridad."""
    valores = {}
    if ARCHIVO_ENV.exists():
        for linea in ARCHIVO_ENV.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip().strip('"').strip("'")
    variables = ("DATABASE_URL", "MODELO_EMBEDDINGS", "DIMENSIONES_EMBEDDINGS", "GEMINI_API_KEY", "MODELO_CHAT", "NIVEL_RAZONAMIENTO", "GROQ_API_KEY")
    valores.update({k: v for k, v in os.environ.items() if k in variables})
    return valores


def conectar():
    """Abre la conexión. Termina con un mensaje claro si falta algo."""
    try:
        import pg8000.dbapi
    except ImportError:
        raise SystemExit("Falta pg8000. Instálalo con:  pip install -r requirements.txt")

    url = leer_env().get("DATABASE_URL", "")
    if not url or "TU-CONTRASEÑA" in url or "[YOUR-PASSWORD]" in url:
        raise SystemExit(
            "No encuentro DATABASE_URL.\n"
            "  1. Copia el archivo .env.example y nómbralo .env (en la raíz del proyecto).\n"
            "  2. Pon ahí la dirección de tu base de datos con tu contraseña.\n"
            "  Ver docs/base-de-datos.md"
        )
    partes = urlsplit(url)
    if partes.scheme not in ("postgres", "postgresql") or not partes.hostname:
        raise SystemExit("DATABASE_URL debe verse así: postgresql://usuario:contraseña@servidor:5432/postgres")

    opciones = parse_qs(partes.query)
    es_local = partes.hostname in ("localhost", "127.0.0.1", "::1")
    modo_ssl = opciones.get("sslmode", ["disable" if es_local else "require"])[0]
    contexto = None
    if modo_ssl in ("verify-full", "verify-ca"):
        contexto = ssl.create_default_context(cafile=opciones.get("sslrootcert", [None])[0])
    elif modo_ssl != "disable":
        # Igual que "sslmode=require" de Postgres: conexión cifrada sin verificar el
        # certificado (Supabase usa una autoridad propia). Para verificarlo, agrega
        # ?sslmode=verify-full&sslrootcert=ruta/al/certificado.crt a DATABASE_URL.
        contexto = ssl.create_default_context()
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE

    try:
        return pg8000.dbapi.connect(
            user=unquote(partes.username or "postgres"),
            password=unquote(partes.password or ""),
            host=partes.hostname,
            port=partes.port or 5432,
            database=(partes.path or "/postgres").lstrip("/") or "postgres",
            ssl_context=contexto,
            timeout=60,
        )
    except Exception as e:
        raise SystemExit(
            f"No pude conectarme a la base de datos ({partes.hostname}): {e}\n"
            "  - Revisa usuario, contraseña y servidor en DATABASE_URL (.env).\n"
            "  - Si la contraseña tiene símbolos como @ # / : hay que codificarlos\n"
            "    (@ = %40, # = %23, / = %2F, : = %3A) o cambiarla por una sin símbolos.\n"
            "  - En Supabase usa la dirección 'Session pooler'."
        )


def sentencias(seccion: str, reemplazos: dict | None = None) -> list[str]:
    """Regresa las sentencias SQL de una sección de backend/esquema.sql."""
    texto = ESQUEMA.read_text(encoding="utf-8")
    bloques = re.split(r"^-- == seccion: (\w+) ==\s*$", texto, flags=re.M)
    disponibles = dict(zip(bloques[1::2], bloques[2::2]))
    if seccion not in disponibles:
        raise SystemExit(f"backend/esquema.sql no tiene la sección '{seccion}'")
    # Quita los comentarios (pueden traer ";" y partirían mal las sentencias)
    sql = "\n".join(re.sub(r"--.*$", "", linea) for linea in disponibles[seccion].splitlines())
    for buscar, poner in (reemplazos or {}).items():
        sql = sql.replace(buscar, poner)
    return [s.strip() for s in sql.split(";") if s.strip()]


def aplicar(conexion, seccion: str, reemplazos: dict | None = None) -> None:
    cursor = conexion.cursor()
    for sentencia in sentencias(seccion, reemplazos):
        cursor.execute(sentencia)


def insertar(conexion, tabla: str, columnas: list[str], filas: list[list],
             conversiones: dict | None = None, al_final: str = "", lote: int = 200) -> int:
    """Inserta muchas filas en pocas idas al servidor (INSERT con varias filas)."""
    conversiones = conversiones or {}
    molde = "(" + ", ".join(f"%s{conversiones.get(c, '')}" for c in columnas) + ")"
    cursor = conexion.cursor()
    total = 0
    for i in range(0, len(filas), lote):
        grupo = filas[i:i + lote]
        sql = (f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES "
               + ", ".join([molde] * len(grupo)) + f" {al_final}")
        cursor.execute(sql, [valor for fila in grupo for valor in fila])
        total += len(grupo)
    return total


def uno(conexion, sql: str, parametros: list | None = None):
    cursor = conexion.cursor()
    cursor.execute(sql, parametros or [])
    fila = cursor.fetchone()
    return fila[0] if fila else None


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
