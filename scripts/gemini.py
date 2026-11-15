"""Llamadas a la API de Gemini (Google) por REST, sin librerías extra.

Lo usan embeddings.py (vectores con gemini-embedding-001) y llm.py (respuestas del chat).
La clave va en .env como GEMINI_API_KEY (se saca en https://aistudio.google.com -> Get API key).
La clave NUNCA se imprime ni se sube a GitHub.

Maneja los límites de uso: si Gemini responde 429 (demasiadas solicitudes) o un error
temporal (5xx), espera y reintenta. Si se agota la cuota del DÍA, se detiene con un
mensaje claro (la carga de fragmentos se puede retomar después con --continuar).
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

BASE = os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta")
TIMEOUT = 60
REINTENTOS = 4


class ErrorGemini(Exception):
    pass


class CuotaAgotada(ErrorGemini):
    """Se acabó la cuota del día (o el proyecto no tiene cuota para ese modelo)."""


def clave_api() -> str:
    from bd import leer_env
    clave = leer_env().get("GEMINI_API_KEY", "").strip()
    if not clave or clave.startswith("TU-"):
        raise SystemExit(
            "No encuentro GEMINI_API_KEY en .env.\n"
            "  1. Entra a https://aistudio.google.com y crea una clave (Get API key).\n"
            "  2. Agrega a tu .env la línea:  GEMINI_API_KEY=tu_clave\n"
            "  Ver docs/base-de-datos.md (sección Gemini)."
        )
    return clave


def _espera_sugerida(cuerpo: str, intento: int) -> float:
    """Gemini a veces indica cuánto esperar ("retryDelay": "17s")."""
    encontrado = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', cuerpo)
    if encontrado:
        return min(float(encontrado.group(1)) + 1, 90)
    return min(2 ** intento, 60)


def llamar(ruta: str, cuerpo: dict | None = None, timeout: float = TIMEOUT, reintentos: int = REINTENTOS) -> dict:
    """POST (o GET si no hay cuerpo) a la API de Gemini con reintentos. `ruta` = 'models/X:metodo'."""
    clave = clave_api()
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    ultimo = ""
    for intento in range(1, reintentos + 1):
        peticion = urllib.request.Request(
            f"{BASE}/{ruta}", data=datos, method="POST" if datos is not None else "GET",
            headers={"Content-Type": "application/json", "x-goog-api-key": clave},
        )
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            texto = e.read().decode("utf-8", "replace")
            ultimo = f"HTTP {e.code}: {texto[:600]}"
            if e.code == 429:
                if re.search(r"PerDay|per day|limit: 0", texto, flags=re.I):
                    raise CuotaAgotada(
                        "Gemini dice que se agotó la cuota diaria (o que tu proyecto no tiene cuota "
                        "para este modelo). Revisa tus límites en https://aistudio.google.com/rate-limit "
                        "y vuelve a intentar más tarde.\n" + ultimo)
                espera = _espera_sugerida(texto, intento)
                print(f"\n   Gemini pide esperar (límite por minuto). Reintento en {espera:.0f} s...")
                time.sleep(espera)
                continue
            if e.code >= 500:
                if intento < reintentos:
                    espera = min(2 ** intento, 30)
                    print(f"   Gemini tuvo un error temporal (HTTP {e.code}). Reintento {intento + 1}/{reintentos} en {espera} s...")
                    time.sleep(espera)
                continue
            if e.code == 400 and "thinking" in texto.lower():
                raise ErrorGemini("Este modelo no acepta NIVEL_RAZONAMIENTO; bórralo de .env o cámbialo.\n" + ultimo)
            if e.code in (400, 403) and ("API key" in texto or "API_KEY" in texto or "PERMISSION_DENIED" in texto):
                raise ErrorGemini("Gemini rechazó la clave GEMINI_API_KEY (¿está bien copiada?).\n" + ultimo)
            if e.code == 404:
                raise ErrorGemini("Gemini no encuentra ese modelo (revisa el nombre en .env).\n" + ultimo)
            raise ErrorGemini(ultimo)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            ultimo = f"{type(e).__name__}: {e}"
            if intento < reintentos:
                espera = min(2 ** intento, 30)
                causa = "no respondió a tiempo" if "timed out" in str(e) else "no pude conectar"
                print(f"   Gemini: {causa} ({ultimo}). Reintento {intento + 1}/{reintentos} en {espera} s...")
                time.sleep(espera)
    raise ErrorGemini(f"Gemini no respondió ({reintentos} intento(s)). Último error: {ultimo}")
