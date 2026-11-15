"""Llamadas a la API de Groq (compatible con OpenAI) por REST, sin librerías extra.

Groq sólo se usa para REDACTAR las respuestas del chat (no tiene modelos de embeddings;
la búsqueda sigue con el modelo de MODELO_EMBEDDINGS).

La clave va en .env como GROQ_API_KEY (https://console.groq.com/keys). Nunca se imprime.
Límites del plan gratis: por modelo y por organización (minuto y día). Si Groq pide
esperar (429), se espera y reintenta; si se acabó lo del día, se avisa claro.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from gemini import ErrorIA

BASE = os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1")
TIMEOUT = 60
REINTENTOS = 3


class ErrorGroq(ErrorIA):
    pass


def clave_api() -> str:
    from bd import leer_env
    clave = leer_env().get("GROQ_API_KEY", "").strip()
    if not clave or clave.startswith("TU-"):
        raise ErrorGroq("No encuentro GROQ_API_KEY en .env. Créala en https://console.groq.com/keys "
                        "y agrega la línea  GROQ_API_KEY=tu_clave")
    return clave


def llamar(ruta: str, cuerpo: dict | None = None, timeout: float = TIMEOUT, reintentos: int = REINTENTOS) -> dict:
    """POST (o GET sin cuerpo) a Groq. `ruta` = 'chat/completions', 'models', etc."""
    clave = clave_api()
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    ultimo = ""
    for intento in range(1, reintentos + 1):
        peticion = urllib.request.Request(
            f"{BASE}/{ruta}", data=datos, method="POST" if datos is not None else "GET",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {clave}",
                     "User-Agent": "flame-in-freefall/0.1"},
        )
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            texto = e.read().decode("utf-8", "replace")
            ultimo = f"HTTP {e.code}: {texto[:500]}"
            if e.code == 401:
                raise ErrorGroq("Groq rechazó la clave GROQ_API_KEY (¿está bien copiada?).\n" + ultimo)
            if e.code == 404 or "model_not_found" in texto or "does not exist" in texto:
                raise ErrorGroq("Groq no encuentra ese modelo (revisa MODELO_CHAT en .env; "
                                "corre scripts/probar_groq.py para ver los disponibles).\n" + ultimo)
            if e.code == 413 or "Request too large" in texto:
                raise ErrorGroq("La pregunta con sus fragmentos es demasiado grande para el límite por minuto "
                                "del plan gratis de Groq. Usa menos fragmentos (k más chico).\n" + ultimo)
            if e.code == 429:
                if "per day" in texto or "(RPD)" in texto or "(TPD)" in texto:
                    raise ErrorGroq("Se acabó la cuota de HOY de Groq para este modelo. Prueba mañana, "
                                    "u otro modelo en MODELO_CHAT.\n" + ultimo)
                try:
                    espera = float(e.headers.get("retry-after") or 0) + 1
                except ValueError:
                    espera = 0
                espera = min(espera or 2 ** intento * 2, 60)
                if intento < reintentos:
                    print(f"   Groq pide esperar (límite por minuto). Reintento en {espera:.0f} s...")
                    time.sleep(espera)
                continue
            if e.code >= 500 or e.code == 498:  # 498 = sin capacidad momentánea
                if intento < reintentos:
                    time.sleep(min(2 ** intento, 20))
                continue
            raise ErrorGroq(ultimo)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            ultimo = f"{type(e).__name__}: {e}"
            if intento < reintentos:
                causa = "no respondió a tiempo" if "timed out" in str(e) else "no pude conectar"
                print(f"   Groq: {causa} ({ultimo}). Reintento {intento + 1}/{reintentos}...")
                time.sleep(min(2 ** intento, 20))
    raise ErrorGroq(f"Groq no respondió ({reintentos} intento(s)). Último error: {ultimo}")
