"""Revisa rápido que la conexión y la clave de Gemini funcionan (no usa la base de datos).

Si el modelo de MODELO_CHAT no responde, prueba otros modelos de texto que tu clave
pueda usar y te dice cuál poner en .env.

Uso:
  python scripts/probar_gemini.py            # prueba el de .env y, si falla, alternativas
  python scripts/probar_gemini.py --todos    # prueba todas las alternativas y compara tiempos
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bd import leer_env  # noqa: E402
from gemini import BASE, ErrorGemini, llamar  # noqa: E402
from llm import MODELO_CHAT_POR_DEFECTO  # noqa: E402

ALTERNATIVAS = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.6-flash",
                "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.5-flash"]
ESPERA = 30  # segundos máximos por modelo


def probar_modelo(modelo: str, nivel: str) -> tuple[bool, str]:
    """Manda una pregunta corta. Regresa (funcionó, detalle)."""
    cuerpo = {"contents": [{"role": "user", "parts": [{"text": "Responde sólo: OK"}]}]}
    if nivel not in ("", "ninguno", "default"):
        cuerpo["generationConfig"] = {"thinkingConfig": {"thinkingLevel": nivel}}
    inicio = time.time()
    try:
        try:
            r = llamar(f"models/{modelo}:generateContent", cuerpo, timeout=ESPERA, reintentos=1)
        except ErrorGemini as e:
            if "NIVEL_RAZONAMIENTO" not in str(e):
                raise
            cuerpo.pop("generationConfig", None)  # este modelo no acepta el ajuste: sin él
            r = llamar(f"models/{modelo}:generateContent", cuerpo, timeout=ESPERA, reintentos=1)
    except ErrorGemini as e:
        primera = str(e).splitlines()[0]
        return False, f"no respondió ({time.time() - inicio:.0f} s): {primera[:160]}"
    partes = (r.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    texto = "".join(p.get("text", "") for p in partes if not p.get("thought")).strip()
    return True, f"respondió en {time.time() - inicio:.1f} s: {texto[:40]!r}"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Prueba la conexión con Gemini.")
    p.add_argument("--todos", action="store_true", help="probar todas las alternativas")
    args = p.parse_args()

    env = leer_env()
    modelo = (env.get("MODELO_CHAT") or MODELO_CHAT_POR_DEFECTO).replace("models/", "")
    nivel = (env.get("NIVEL_RAZONAMIENTO") or "low").strip().lower()

    print(f"1) Conexión con {BASE} y clave...")
    inicio = time.time()
    try:
        modelos = llamar("models?pageSize=200", timeout=20, reintentos=2).get("models", [])
    except ErrorGemini as e:
        raise SystemExit(f"   FALLÓ: {e}")
    nombres = {m["name"].replace("models/", "") for m in modelos}
    print(f"   OK en {time.time() - inicio:.1f} s; tu clave ve {len(nombres)} modelos.")

    print("2) Vectores con gemini-embedding-001...")
    inicio = time.time()
    try:
        r = llamar("models/gemini-embedding-001:batchEmbedContents", {"requests": [{
            "model": "models/gemini-embedding-001", "content": {"parts": [{"text": "llama fría"}]},
            "taskType": "RETRIEVAL_QUERY", "outputDimensionality": 768}]},
            timeout=ESPERA, reintentos=1)
        recibidas = len(r["embeddings"][0]["values"])
        aviso = "" if recibidas == 768 else " (se pidieron 768; el script las recorta, no hay problema)"
        print(f"   OK en {time.time() - inicio:.1f} s ({recibidas} dimensiones{aviso}).")
    except ErrorGemini as e:
        print(f"   FALLÓ: {str(e).splitlines()[0][:200]}")

    print(f"3) Pregunta corta a los modelos de texto (máximo {ESPERA} s cada uno):")
    candidatos = [modelo] + [m for m in ALTERNATIVAS if m != modelo and m in nombres]
    funcionan = []
    for m in candidatos:
        nivel_m = nivel if m == modelo else ("minimal" if "lite" not in m else "ninguno")
        ok, detalle = probar_modelo(m, nivel_m)
        print(f"   {'OK ' if ok else 'X  '} {m}: {detalle}")
        if ok:
            funcionan.append((m, nivel_m))
            if not args.todos:
                break

    if not funcionan:
        print("\nNingún modelo de texto respondió. La clave y la conexión sí funcionan (paso 1), así que\n"
              "probablemente Google está saturado o tu proyecto no tiene cuota para esos modelos.\n"
              "Revisa https://aistudio.google.com/rate-limit e intenta en unos minutos.")
        return 1
    elegido, nivel_e = funcionan[0]
    if elegido == modelo:
        print(f"\nTodo bien con {modelo}. Ya puedes usar:  python scripts/preguntar.py \"tu pregunta\"")
    else:
        print("\nPon esto en tu .env (y guarda con Ctrl+S):")
        print(f"   MODELO_CHAT={elegido}")
        print(f"   NIVEL_RAZONAMIENTO={nivel_e}")
        print("Luego:  python scripts/preguntar.py \"tu pregunta\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
