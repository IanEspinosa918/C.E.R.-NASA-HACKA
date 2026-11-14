"""Limpia las pruebas de SAME (PSI-102) y SAME-R (PSI-101) al formato común.

SAME = Smoke Aerosol Measurement Experiment. NO quema con flama: calienta materiales de
la nave con un alambre eléctrico hasta que sueltan humo (pirólisis), como un cable o un
componente sobrecalentado. Es la etapa más temprana de un incendio, justo cuando hay que
detectarlo. Mide el tamaño de las partículas de humo en microgravedad para saber qué
tipo de detector las ve.

Entrada:  data/raw/PSI-102_SAME/Experimental table/*.csv
          data/raw/PSI-101_SAME-R/Experimental table/*.csv
Salida:   data/processed/pruebas_same.csv
Reporte:  data/reportes/validacion_same.csv

Cómo se interpreta (según los reportes finales de SAME y SAME-R):
  - SAME: 4 condiciones con Teflón; las filas 5-8 dicen "same conditions as 1-4" para
    Kapton, silicona, mecha de lámpara y ftalato de dibutilo -> se expanden a 4 pruebas
    cada una (20 pruebas en total).
  - SAME-R (vuelo de julio a septiembre de 2010): las filas terminadas en "a" (51a, 61a...)
    son el MISMO humo medido otra vez después de envejecer, no pruebas nuevas.
  - Rt/R0 = razón de resistencia del alambre calefactor: indica qué tan caliente estaba
    (más alto = más caliente). El propio reporte aclara que es aproximado: dos pruebas con
    el mismo Rt/R0 pueden tener temperaturas distintas.
  - El RESULTADO (tamaño de las partículas) NO está en estas tablas, sólo en los reportes.

Uso:  python scripts/limpiar_same.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun_limpieza as cl  # noqa: E402

MATERIALES = {
    "teflon": "Teflón (PTFE)",
    "kapton": "Kapton (poliimida, aislante de cables)",
    "silicone": "Silicona",
    "silicone rubber": "Silicona",
    "lampwick": "Mecha de lámpara (algodón)",
    "pyrell": "Pyrell (espuma retardante de fuego)",
    "dibutyl phthalate": "Ftalato de dibutilo (líquido de prueba)",
}

NIVELES = [("high", "calentamiento alto"), ("mid", "calentamiento medio"),
           ("low temp", "calentamiento bajo"), ("baseline", "condición base"), ("b.l.", "condición base")]


def material(texto: str) -> str:
    return MATERIALES.get(texto.strip().lower(), texto.strip())


def base(psi_id: str, nombre: str, carpeta: Path, archivo: Path, fila: int) -> dict:
    return {
        "experimento_id": psi_id, "experimento": nombre, "gravedad": "microgravedad",
        "tipo_combustible": "humo", "doi": cl.doi_de(psi_id), "fila_origen": fila,
        "archivo_origen": f"{carpeta.name}/Experimental table/{archivo.name}",
        "banderas": "resultado_en_reportes_no_en_tabla", "aproximado": False, "resultado": "",
    }


def same() -> list[dict]:
    psi_id, nombre = "PSI-102", "SAME"
    carpeta = cl.carpeta_experimento(psi_id)
    archivo = next((carpeta / "Experimental table").glob("*.csv"))
    encabezados, filas = cl.leer_csv(archivo)
    if not (encabezados[1].startswith("Sample Material") and encabezados[3].startswith("Weight loss")):
        raise SystemExit("El CSV de SAME cambió de columnas. Revísalo antes de seguir.")

    condiciones, pruebas = [], []
    for numero_fila, f in filas:
        f = (f + [""] * 5)[:5]
        texto_material = f[1].strip()
        if "same conditions as" in texto_material.lower():
            nombre_mat = texto_material.split(":")[0]
            for i, cond in enumerate(condiciones, start=1):
                p = base(psi_id, nombre, carpeta, archivo, numero_fila)
                p.update(cond)
                p.update({
                    "prueba_id": f"{f[0].strip()}.{i}",
                    "combustible": material(nombre_mat), "descripcion_muestra": nombre_mat,
                    "notas": f"condiciones copiadas de la prueba {cond['_origen']} (la tabla dice "
                             f"'same conditions as 1-4'); calentamiento con alambre, sin flama",
                })
                pruebas.append(p)
            continue
        cond = {
            "flujo_aire_cm_s": cl.numero(f[2])[0],
            "perdida_masa_mg_min": cl.numero(f[3])[0],
            "tiempo_envejecimiento_s": None if cl.numero(f[4])[0] is None else cl.numero(f[4])[0] * 60,
            "_origen": f[0].strip(),
        }
        condiciones.append(cond)
        p = base(psi_id, nombre, carpeta, archivo, numero_fila)
        p.update(cond)
        p.update({"prueba_id": f[0].strip(), "combustible": material(texto_material),
                  "descripcion_muestra": texto_material,
                  "notas": "calentamiento con alambre, sin flama"})
        pruebas.append(p)
    return pruebas


def same_r() -> list[dict]:
    psi_id, nombre = "PSI-101", "SAME-R"
    carpeta = cl.carpeta_experimento(psi_id)
    archivo = next((carpeta / "Experimental table").glob("*.csv"))
    encabezados, filas = cl.leer_csv(archivo)
    if not (encabezados[1].startswith("SAME Test") and encabezados[5] == "Rt/R0"
            and encabezados[9].startswith("Net aging")):
        raise SystemExit("El CSV de SAME-R cambió de columnas. Revísalo antes de seguir.")

    pruebas = []
    for numero_fila, f in filas:
        f = (f + [""] * 10)[:10]
        prueba = f[1].strip()
        descripcion = f[2].strip()
        envejecido = bool(re.fullmatch(r"\d+a", prueba))
        notas = ["calentamiento con alambre, sin flama"]
        if envejecido:
            notas.append(f"mismo humo de la prueba {prueba[:-1]}, medido otra vez después de envejecer")
        nivel = next((texto for clave, texto in NIVELES if clave in descripcion.lower()), "")
        if nivel:
            notas.append(nivel)
        if "no flow" in descripcion.lower():
            notas.append("sin flujo de aire: el humo sólo se mueve por difusión")
        if "sts det" in descripcion.lower():
            notas.append("medición con el detector de humo del transbordador (STS)")
        if descripcion:
            notas.append(f"descripción original: {descripcion}")
        if f[7].strip() or f[8].strip():
            notas.append(f"envejecimiento primario {f[7].strip() or '-'} s, mezcla {f[8].strip() or '-'} s")

        fecha = cl.fecha_iso(f"{f[3].strip()}-10") if f[3].strip() else ""  # vuelo en 2010

        p = base(psi_id, nombre, carpeta, archivo, numero_fila)
        p.update({
            "prueba_id": prueba, "fecha": fecha,
            "combustible": material(f[0]), "descripcion_muestra": f[0].strip(),
            "flujo_aire_cm_s": cl.numero(f[4])[0],
            "calentamiento_rt_r0": cl.numero(f[5])[0],
            "tiempo_calentamiento_s": cl.numero(f[6])[0],
            "tiempo_envejecimiento_s": cl.numero(f[9])[0],
            "resultado_original": descripcion,
            "aproximado": True,  # Rt/R0 es un indicador aproximado de temperatura
            "notas": "; ".join(notas),
        })
        pruebas.append(p)
    return pruebas


def main() -> None:
    pruebas = same() + same_r()
    for p in pruebas:
        p.pop("_origen", None)
    problemas = cl.validar(pruebas)
    salida, reporte = cl.escribir("same", pruebas, problemas)
    cl.resumen("SAME / SAME-R", pruebas, problemas, salida, reporte)
    from collections import Counter
    mats = Counter(f"{p['experimento']}: {p['combustible'].split(' (')[0]}" for p in pruebas)
    print("   Materiales:", ", ".join(f"{k}={v}" for k, v in sorted(mats.items())))
    flujos = Counter(p["flujo_aire_cm_s"] for p in pruebas if p["experimento"] == "SAME-R")
    print("   Flujos SAME-R (cm/s):", ", ".join(f"{k:g}={v}" for k, v in sorted(flujos.items())))
    print("   Nota: el tamaño de las partículas (resultado) está en los reportes finales, no en las tablas.")


if __name__ == "__main__":
    main()
