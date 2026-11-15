"""Revisa rápido que la clave de Groq funciona y qué modelos de texto puedes usar (sin base de datos).

Uso:
  python scripts/probar_groq.py                         # prueba MODELO_CHAT de .env (u openai/gpt-oss-120b)
  python scripts/probar_groq.py --modelo openai/gpt-oss-20b
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bd import leer_env  # noqa: E402
from groq_api import BASE, ErrorGroq, llamar  # noqa: E402

POR_DEFECTO = "openai/gpt-oss-120b"
NO_TEXTO = ("whisper", "orpheus", "prompt-guard", "safeguard", "tts", "guard")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Prueba la conexión con Groq.")
    p.add_argument("--modelo", help=f"modelo a probar (default: MODELO_CHAT de .env o {POR_DEFECTO})")
    args = p.parse_args()
    env = leer_env()
    modelo = args.modelo or env.get("MODELO_CHAT", "")
    if not modelo or modelo.startswith("gemini"):
        modelo = POR_DEFECTO

    print(f"1) Conexión con {BASE} y clave...")
    inicio = time.time()
    try:
        modelos = llamar("models", timeout=20, reintentos=2).get("data", [])
    except ErrorGroq as e:
        raise SystemExit(f"   FALLÓ: {e}")
    texto = sorted(m["id"] for m in modelos if m.get("active", True)
                   and not any(x in m["id"] for x in NO_TEXTO))
    print(f"   OK en {time.time() - inicio:.1f} s. Modelos de texto disponibles con tu clave:")
    for m in texto:
        print(f"     - {m}")

    print(f"2) Pregunta corta a {modelo}...")
    cuerpo = {"model": modelo, "messages": [{"role": "user", "content": "Responde sólo: OK"}],
              "max_completion_tokens": 300}
    if "gpt-oss" in modelo:
        cuerpo.update({"reasoning_effort": "low", "include_reasoning": False})
    inicio = time.time()
    try:
        r = llamar("chat/completions", cuerpo, timeout=30, reintentos=1)
    except ErrorGroq as e:
        raise SystemExit(f"   FALLÓ: {e}")
    respuesta = ((r.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
    print(f"   OK en {time.time() - inicio:.1f} s; respondió: {respuesta[:60]!r}")
    print("\nPon esto en tu .env (y guarda con Ctrl+S):")
    print(f"   MODELO_CHAT={modelo}")
    print("   NIVEL_RAZONAMIENTO=low")
    print("Luego:  python scripts/preguntar.py \"tu pregunta\"   o reinicia  python backend/app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
