"""Prueba el chat completo (RAG): busca fragmentos en la base y Gemini redacta la respuesta con citas.

Es exactamente lo que hará el endpoint /chat del backend en la Fase 2.

Necesita en .env:  DATABASE_URL, GEMINI_API_KEY  (y opcional MODELO_CHAT).
La búsqueda usa el mismo modelo de embeddings con el que se cargaron los fragmentos
(puede ser el local o Gemini; son independientes del modelo que redacta).

Uso:
  python scripts/preguntar.py "¿qué son las llamas frías y por qué importan para la seguridad?"
  python scripts/preguntar.py "how does CO2 affect droplet extinction?" -k 10
  python scripts/preguntar.py "¿qué tan rápido se propaga el fuego en telas?" --experimento PSI-62
  python scripts/preguntar.py "..." --ver-fragmentos      # muestra también lo que se le mandó
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bd  # noqa: E402
from buscar import buscar, con_vecinos, preparar  # noqa: E402
from llm import fuentes_citadas, responder  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Pregunta al chat (RAG + Gemini).")
    p.add_argument("pregunta")
    p.add_argument("-k", type=int, default=8, help="fragmentos que se le dan al modelo (default 8)")
    p.add_argument("--experimento", default="", help="sólo este experimento (ej. PSI-69)")
    p.add_argument("--pilar", default="", help="prevencion | deteccion | supresion | contexto")
    p.add_argument("--modelo-chat", help="modelo que redacta (default: MODELO_CHAT de .env o gemini-flash-latest)")
    p.add_argument("--sin-vecinos", action="store_true", help="no agregar los fragmentos vecinos")
    p.add_argument("--ver-fragmentos", action="store_true", help="mostrar los fragmentos encontrados")
    args = p.parse_args()

    from gemini import ErrorGemini
    conexion = bd.conectar()
    vectorizador = preparar(conexion)
    print("Buscando fragmentos en la base...")
    try:
        fragmentos = buscar(conexion, vectorizador, args.pregunta, args.k, args.experimento, args.pilar)
    except ErrorGemini as e:
        raise SystemExit(f"Error al vectorizar la pregunta con Gemini:\n{e}")
    if not args.sin_vecinos:
        fragmentos = con_vecinos(conexion, fragmentos)

    if args.ver_fragmentos:
        print("Fragmentos encontrados:")
        for n, f in enumerate(fragmentos, 1):
            print(f"  [{n}] {f['similitud']:.3f}  {f['experimento']}  {f['archivo']}  "
                  f"{f['texto'][:110].replace(chr(10), ' ')}...")
        print()

    from bd import leer_env
    modelo_chat = args.modelo_chat or leer_env().get("MODELO_CHAT") or "gemini-flash-latest"
    print(f"Preguntando a Gemini ({modelo_chat}); suele tardar de 5 a 30 segundos...\n")
    try:
        texto = responder(args.pregunta, fragmentos, modelo_chat)
    except ErrorGemini as e:
        raise SystemExit(f"Error al pedir la respuesta a Gemini:\n{e}")

    print(texto)
    citadas = fuentes_citadas(texto, fragmentos)
    if citadas:
        print("\nFuentes:")
        for n, f in citadas:
            pagina = f", pág. {f['pagina']}" if f.get("pagina") else ""
            doi = f"  doi:{f['doi']}" if f.get("doi") else ""
            print(f"  [{n}] {f['experimento']} — {f.get('titulo_documento') or f['archivo']}{pagina}{doi}")
    else:
        print("\n(La respuesta no citó fragmentos: tómala con cuidado.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
