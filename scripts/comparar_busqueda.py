"""Compara la búsqueda con dos modelos de embeddings (por ejemplo, el local contra Gemini).

Cada modelo tiene su propia tabla (fragmentos y fragmentos_gemini), así que se pueden
comparar lado a lado con las mismas preguntas antes de decidir cuál usar en el chat.
No llama al modelo de chat: sólo muestra qué fragmentos encuentra cada uno.

Uso:
  python scripts/comparar_busqueda.py                       # preguntas de prueba incluidas
  python scripts/comparar_busqueda.py "¿qué son las llamas frías?" "¿qué midió SAME?"
  python scripts/comparar_busqueda.py --a sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
                                      --b gemini-embedding-001 -k 6
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bd  # noqa: E402
from buscar import buscar, preparar  # noqa: E402
from embeddings import MODELO_POR_DEFECTO  # noqa: E402
from fuentes_generales import nombre_fuente  # noqa: E402

PREGUNTAS = [
    "¿qué son las llamas frías?",
    "¿Por qué un flujo de aire muy bajo puede apagar una llama en microgravedad?",
    "¿Cuántas pruebas de gotas hizo FLEX con decano?",
    "¿Qué estudió el experimento Saffire y dónde se hizo?",
    "¿Por qué el tamaño de las partículas de humo importa para los detectores?",
    "¿Qué efecto tienen el CO2 y el helio como diluyentes en la extinción de gotas?",
    "¿Un material que pasa la prueba de inflamabilidad en la Tierra puede arder en microgravedad?",
    "¿qué puede provocar un incendio en una nave?",
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Compara dos modelos de embeddings en la búsqueda.")
    p.add_argument("preguntas", nargs="*")
    p.add_argument("--a", default=MODELO_POR_DEFECTO, help="modelo A (default: el local)")
    p.add_argument("--b", default="gemini-embedding-001", help="modelo B (default: Gemini)")
    p.add_argument("-k", type=int, default=6)
    args = p.parse_args()

    conexion = bd.conectar()
    modelos = []
    for nombre in (args.a, args.b):
        v = preparar(conexion, nombre)
        total = bd.uno(conexion, f"SELECT count(*) FROM {v.tabla}")
        print(f"{v.nombre}: tabla {v.tabla} con {total} fragmentos")
        modelos.append(v)
    if len({bd.uno(conexion, f'SELECT count(*) FROM {v.tabla}') for v in modelos}) > 1:
        print("AVISO: las tablas no tienen el mismo número de fragmentos (¿carga incompleta?); "
              "la comparación no es justa hasta que estén completas.")

    for pregunta in args.preguntas or PREGUNTAS:
        print(f"\n{'=' * 100}\n{pregunta}")
        resultados = [buscar(conexion, v, pregunta, args.k) for v in modelos]
        for etiqueta, v, lista in zip("AB", modelos, resultados):
            print(f"\n  [{etiqueta}] {v.nombre}")
            for i, f in enumerate(lista, 1):
                pagina = f" p.{f['pagina']}" if f.get("pagina") else ""
                print(f"    {i}. {f['similitud']:.2f} {f.get('via', ''):11} {nombre_fuente(f)[:28]:28} "
                      f"{(f.get('titulo_documento') or '')[:40]}{pagina} | {f['texto'][:70].replace(chr(10), ' ')}")
        comunes = {(f["archivo"], f["orden"]) for f in resultados[0]} & {(f["archivo"], f["orden"]) for f in resultados[1]}
        print(f"\n  En común: {len(comunes)} de {args.k}")
    print("\nCalifica cuál trae fragmentos más útiles para cada pregunta. Si B gana claramente, pon en .env:\n"
          f"  MODELO_EMBEDDINGS={args.b}\n  y reinicia el backend.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
