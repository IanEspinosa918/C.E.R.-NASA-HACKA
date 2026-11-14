"""Corre todos los scripts de limpieza y junta el resultado en una sola tabla.

Salida: data/processed/pruebas.csv  (todas las pruebas, formato común)

Para agregar un experimento nuevo: crear scripts/limpiar_<nombre>.py con una
función main() que escriba data/processed/pruebas_<nombre>.csv, y agregarlo
a LIMPIADORES.

Uso:  python scripts/limpiar_todo.py
"""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun_limpieza as cl  # noqa: E402

LIMPIADORES = [
    "limpiar_flex",
    "limpiar_bass2",
    "limpiar_cfi",
    "limpiar_saffire",
    # "limpiar_cfig",
    # "limpiar_bass",
    # "limpiar_same",
]


def main() -> int:
    fallas = []
    for nombre in LIMPIADORES:
        try:
            importlib.import_module(nombre).main()
        except SystemExit as e:
            print(f"\n!! {nombre}: {e}")
            fallas.append(nombre)
        except Exception as e:  # seguir con los demás
            print(f"\n!! {nombre} falló: {e}")
            fallas.append(nombre)

    partes = sorted(cl.DIR_PROCESSED.glob("pruebas_*.csv"))
    total = 0
    with open(cl.DIR_PROCESSED / "pruebas.csv", "w", newline="", encoding="utf-8") as salida:
        w = csv.DictWriter(salida, fieldnames=cl.COLUMNAS)
        w.writeheader()
        for parte in partes:
            with open(parte, encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    w.writerow({c: fila.get(c, "") for c in cl.COLUMNAS})
                    total += 1

    print(f"\n========== {total} pruebas en data/processed/pruebas.csv ==========")
    if fallas:
        print("Con errores:", ", ".join(fallas))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
