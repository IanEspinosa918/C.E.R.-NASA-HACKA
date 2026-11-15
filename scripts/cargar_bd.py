"""Crea las tablas `experimentos` y `pruebas` en Postgres y carga los datos limpios.

Entrada:  data/raw/<experimento>/ficha.json     (de scripts/descargar_psi.py)
          data/processed/pruebas.csv            (de scripts/limpiar_todo.py)
Destino:  la base de datos de DATABASE_URL (archivo .env)

Se puede correr las veces que haga falta: cada vez deja las dos tablas iguales a los
archivos (actualiza los experimentos y vuelve a cargar todas las pruebas).

Uso:
  python scripts/cargar_bd.py              # crea/actualiza experimentos y pruebas
  python scripts/cargar_bd.py --recrear    # borra TODAS las tablas (también fragmentos) y empieza de cero
  python scripts/cargar_bd.py --revisar    # no cambia nada; sólo muestra qué hay en la base
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bd  # noqa: E402
import comun_limpieza as cl  # noqa: E402
from investigaciones import CATALOGO, TIERRA, TODAS  # noqa: E402

COLUMNAS_NUMERICAS = set(cl.RANGOS) | {"fila_origen"}


def fecha(texto: str):
    """'04-18-2017' (formato de las fichas) o '2009-03-05' -> date; vacío -> None."""
    texto = (texto or "").strip()
    for formato in ("%m-%d-%Y", "%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def leer_experimentos() -> list[dict]:
    experimentos = []
    for psi_id, alias in TODAS.items():
        ficha = json.loads((cl.carpeta_experimento(psi_id) / "ficha.json").read_text(encoding="utf-8"))
        pilar, combustible, familia, resumen = CATALOGO[psi_id]
        publicaciones = [
            {"titulo": (p.get("title") or "").strip(), "autores": (p.get("authorList") or "").strip(),
             "doi": (p.get("doi") or "").strip()}
            for p in (ficha.get("publications") or [])
        ]
        relacionados = [r.strip() for r in (ficha.get("related_glds") or "").split(",") if r.strip()]
        experimentos.append({
            "id": psi_id,
            "acronimo": (ficha.get("investigationAcronym") or alias).strip(),
            "titulo": (ficha.get("title") or "").strip(),
            "tipo": "tierra" if psi_id in TIERRA else "vuelo",
            "pilar": pilar, "tipo_combustible": combustible, "familia_equipo": familia,
            "resumen_es": resumen,
            "hardware": (ficha.get("experimentHardware") or "").strip(),
            "plataforma": (ficha.get("flightProgram") or "").strip(),
            "centro_nasa": (ficha.get("managingNasaCenter") or "").strip(),
            "tipo_proyecto": (ficha.get("projectType") or "").strip(),
            "fecha_inicio": fecha(ficha.get("investigationStartDate")),
            "fecha_fin": fecha(ficha.get("investigationEndDate")),
            "doi": (ficha.get("doi") or "").strip(),
            "version": ficha.get("version"),
            "area": (ficha.get("researchArea") or "").strip(),
            "subarea": (ficha.get("subResearchArea") or "").strip(),
            "objetivo": (ficha.get("objective") or "").strip(),
            "enfoque": (ficha.get("approach") or "").strip(),
            "hipotesis": (ficha.get("hypothesis") or "").strip(),
            "impacto": (ficha.get("researchImpacts") or "").strip(),
            "relacionados": relacionados,
            "publicaciones": json.dumps(publicaciones, ensure_ascii=False),
            "url": f"https://psi.nasa.gov/physci/repo/data/investigations/{psi_id}",
            "licencia": (ficha.get("licenseIdentifier") or "").strip(),
        })
    return experimentos


def leer_pruebas() -> tuple[list[str], list[list]]:
    archivo = cl.DIR_PROCESSED / "pruebas.csv"
    if not archivo.exists():
        raise SystemExit("No existe data/processed/pruebas.csv. Corre primero: python scripts/limpiar_todo.py")
    with open(archivo, encoding="utf-8") as f:
        lector = csv.DictReader(f)
        columnas = list(lector.fieldnames or [])
        filas = []
        for fila in lector:
            valores = []
            for c in columnas:
                v = fila[c]
                if c in COLUMNAS_NUMERICAS:
                    v = None if v == "" else (int(float(v)) if c == "fila_origen" else float(v))
                elif c == "fecha":
                    v = fecha(v)
                elif c == "aproximado":
                    v = (v == "si")
                valores.append(v)
            filas.append(valores)
    return columnas, filas


def revisar(conexion) -> None:
    existe = bd.uno(conexion, "SELECT to_regclass('public.experimentos') IS NOT NULL")
    if not existe:
        print("La base todavía no tiene tablas. Corre: python scripts/cargar_bd.py")
        return
    print(f"experimentos: {bd.uno(conexion, 'SELECT count(*) FROM experimentos')}")
    if bd.uno(conexion, "SELECT to_regclass('public.pruebas') IS NOT NULL"):
        print(f"pruebas:      {bd.uno(conexion, 'SELECT count(*) FROM pruebas')}")
        cursor = conexion.cursor()
        cursor.execute("SELECT pilar, count(*), sum(num_pruebas) FROM experimentos_resumen GROUP BY pilar ORDER BY pilar")
        for pilar, n, pruebas in cursor.fetchall():
            print(f"   {pilar:11} {n:2} experimentos, {int(pruebas or 0):4} pruebas")
    if bd.uno(conexion, "SELECT to_regclass('public.fragmentos') IS NOT NULL"):
        print(f"fragmentos:   {bd.uno(conexion, 'SELECT count(*) FROM fragmentos')}")
    else:
        print("fragmentos:   (tabla sin crear; corre scripts/cargar_fragmentos.py)")


def main() -> int:
    p = argparse.ArgumentParser(description="Carga experimentos y pruebas a Postgres.")
    p.add_argument("--recrear", action="store_true", help="borra todas las tablas antes de cargar")
    p.add_argument("--revisar", action="store_true", help="sólo muestra qué hay en la base")
    args = p.parse_args()

    conexion = bd.conectar()
    if args.revisar:
        revisar(conexion)
        return 0

    experimentos = leer_experimentos()
    columnas, pruebas = leer_pruebas()

    cursor = conexion.cursor()
    if args.recrear:
        print("Borrando tablas (fragmentos, pruebas, experimentos)...")
        cursor.execute("DROP TABLE IF EXISTS fragmentos, pruebas, experimentos CASCADE")
    else:
        cursor.execute("DROP VIEW IF EXISTS experimentos_resumen")
        cursor.execute("DROP TABLE IF EXISTS pruebas")

    bd.aplicar(conexion, "experimentos")
    campos = list(experimentos[0].keys())
    actualizar = ", ".join(f"{c} = EXCLUDED.{c}" for c in campos if c != "id")
    bd.insertar(conexion, "experimentos", campos, [[e[c] for c in campos] for e in experimentos],
                conversiones={"relacionados": "::text[]", "publicaciones": "::jsonb",
                              "fecha_inicio": "::date", "fecha_fin": "::date", "version": "::integer"},
                al_final=f"ON CONFLICT (id) DO UPDATE SET {actualizar}", lote=10)

    bd.aplicar(conexion, "pruebas")
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'pruebas'")
    en_tabla = {f[0] for f in cursor.fetchall()}
    faltan = [c for c in columnas if c not in en_tabla]
    if faltan:
        conexion.rollback()
        raise SystemExit(f"pruebas.csv tiene columnas que no están en backend/esquema.sql: {faltan}.\n"
                         "Agrégalas a la tabla `pruebas` del esquema y vuelve a correr.")
    conversiones = {c: "::double precision" for c in columnas if c in COLUMNAS_NUMERICAS}
    conversiones.update({"fila_origen": "::integer", "fecha": "::date", "aproximado": "::boolean"})
    bd.insertar(conexion, "pruebas", columnas, pruebas, conversiones=conversiones)
    conexion.commit()

    print(f"Listo: {len(experimentos)} experimentos y {len(pruebas)} pruebas cargados.\n")
    revisar(conexion)
    return 0


if __name__ == "__main__":
    sys.exit(main())
