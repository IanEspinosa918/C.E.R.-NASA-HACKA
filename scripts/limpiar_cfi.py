"""Limpia las pruebas de CFI, Cool Flames Investigation (PSI-39), al formato común.

CFI quemó gotas de n-dodecano, mezclas con iso-dodecano y farnesano (biocombustible)
en la ISS, de 0.5 a 5 atm, para estudiar las LLAMAS FRÍAS: la llama caliente (visible)
se apaga, pero la gota sigue reaccionando con una llama fría casi invisible.

Entrada:  data/raw/PSI-39_CFI/Science Documents/PSI-39_Science Documents_CFI_DataSummary_Spreadsheet_Jan2021.xlsx
          (el CSV de "Experimental table" sólo trae condiciones de 87 pruebas, sin resultados;
           el Excel tiene las 227 pruebas, con resultados en la hoja DATA)
Salida:   data/processed/pruebas_cfi.csv
Reporte:  data/reportes/validacion_cfi.csv

Hojas usadas (se unen por "Flex Number"):
  Master Sheet -> fecha, presión, O2/N2/He, si la gota iba en fibra, combustible
  DATA         -> D0, Dext hot, khot, kcool, Dext cool, reencendidos, tiempo de llama caliente
  Comments     -> notas de la tripulación/investigadores (útiles para la IA)

Cómo se decide el resultado:
  - Hay kcool                 -> "llama_fria" (se apagó la caliente y siguió una fría)
  - Hay Dext hot sin kcool    -> "extincion"
  - Hay D0 sin lo anterior    -> "encendio"
  - Sin análisis numérico     -> vacío (79 pruebas; el comentario sí describe la prueba)
  - "Extrap CF?" = 1          -> los valores de la llama fría fueron extrapolados -> aproximado
  - "Dext,cool" = 0           -> la llama fría consumió toda la gota

Requiere openpyxl:  pip install openpyxl
Uso:  python scripts/limpiar_cfi.py
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun_limpieza as cl  # noqa: E402

PSI_ID = "PSI-39"
NOMBRE = "CFI"

COMBUSTIBLES = {
    "c12h26": "n-Dodecano",
    "[.60]/[.40] c12h26/iso-dodecane": "n-Dodecano / iso-dodecano (60/40)",
    "[.75]/[.25] c12h26/iso-dodecane": "n-Dodecano / iso-dodecano (75/25)",
    "farnesane": "Farnesano (biocombustible)",
}


def hoja(libro, nombre: str) -> dict[str, tuple]:
    """Lee una hoja y regresa {Flex Number: fila} (sin el encabezado)."""
    filas = [f for f in libro[nombre].iter_rows(values_only=True)
             if f and any(c not in (None, "") for c in f)]
    return {str(f[0]).strip(): f for f in filas[1:]}, [str(h).strip() if h else "" for h in filas[0]]


def num(valor):
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return None if valor != valor else float(valor)  # NaN -> None
    return cl.numero(valor)[0]


def limpiar() -> list[dict]:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("Falta openpyxl. Instálalo con:  pip install openpyxl")

    carpeta = cl.carpeta_experimento(PSI_ID)
    archivo = next((carpeta / "Science Documents").glob("*CFI_DataSummary*.xlsx"))
    libro = openpyxl.load_workbook(archivo, read_only=True, data_only=True)

    master, enc_m = hoja(libro, "Master Sheet")
    datos, enc_d = hoja(libro, "DATA")
    comentarios, _ = hoja(libro, "Comments")

    if not (enc_m[0].startswith("Flex Number") and enc_m[5] == "Oxygen" and enc_m[9].startswith("Fuel")
            and enc_d[1].startswith("D0") and enc_d[4].startswith("kcool") and enc_d[9] == "HF Burn Time"):
        raise SystemExit("El Excel de CFI cambió de columnas. Revisa el archivo antes de seguir.")

    doi = cl.doi_de(PSI_ID)
    pruebas = []
    for fila_n, (flex, m) in enumerate(master.items(), start=2):
        d = datos.get(flex, (None,) * 20)
        comentario = str((comentarios.get(flex) or (None, ""))[1] or "").strip()

        d0, dext_hot, khot = num(d[1]), num(d[2]), num(d[3])
        kcool, dext_cool = num(d[4]), num(d[5])
        extrapolado = d[8] == 1

        if kcool is not None:
            resultado = "llama_fria"
        elif dext_hot is not None:
            resultado = "extincion"
        elif d0 is not None:
            resultado = "encendio"
        else:
            resultado = ""

        banderas = []
        if resultado == "":
            banderas.append("sin_analisis_numerico")

        notas = []
        fibra = str(m[8] or "").strip().lower()
        notas.append("gota sostenida en fibra" if fibra == "yes" else
                     "gota libre (sin fibra)" if fibra == "no" else "fibra: sin dato")
        if dext_cool == 0:
            notas.append("la llama fría consumió toda la gota")
        if extrapolado:
            notas.append("valores de llama fría extrapolados por los investigadores")
        if num(d[7]) is not None:
            notas.append(f"reencendidos: {int(num(d[7]))}")
        notas.append(f"CIR {str(m[3]).strip()}")
        if comentario:
            notas.append(f"Comentario: {comentario}")

        fecha = m[1].strftime("%Y-%m-%d") if isinstance(m[1], datetime) else cl.fecha_iso(str(m[1]))
        combustible_original = str(m[9] or "").strip()

        pruebas.append({
            "experimento_id": PSI_ID,
            "experimento": NOMBRE,
            "prueba_id": flex,
            "fecha": fecha,
            "gravedad": "microgravedad",
            "tipo_combustible": "gota",
            "combustible": COMBUSTIBLES.get(combustible_original.lower(), combustible_original),
            "descripcion_muestra": combustible_original,
            "geometria": "gota",
            "presion_atm": num(d[6]) if num(d[6]) is not None else num(m[4]),
            "o2": num(m[5]), "n2": num(m[6]), "he": num(m[7]), "co2": 0.0,
            "flujo_aire_cm_s": None,  # aire quieto
            "diametro_inicial_mm": d0,
            "diametro_extincion_mm": dext_hot,
            "k_quemado_mm2_s": khot,
            "k_quemado_fria_mm2_s": kcool,
            "diametro_extincion_fria_mm": dext_cool,
            "tiempo_quemado_s": num(d[9]),  # duración de la llama caliente
            "resultado": resultado,
            "resultado_original": f"Completed Analysis? {str(d[19] or '').strip()}",
            "aproximado": extrapolado,
            "banderas": ";".join(banderas),
            "notas": "; ".join(notas),
            "doi": doi,
            "archivo_origen": f"{carpeta.name}/Science Documents/{archivo.name}",
            "fila_origen": fila_n,
        })
    return pruebas


def main() -> None:
    pruebas = limpiar()
    problemas = cl.validar(pruebas)
    salida, reporte = cl.escribir("cfi", pruebas, problemas)
    cl.resumen(NOMBRE, pruebas, problemas, salida, reporte)
    combustibles = Counter(p["combustible"] for p in pruebas)
    print("   Combustibles:", ", ".join(f"{k}={v}" for k, v in combustibles.most_common()))
    presiones = Counter(p["presion_atm"] for p in pruebas)
    print("   Presiones (atm):", ", ".join(f"{k:g}={v}" for k, v in sorted(presiones.items())))
    sin = sum(1 for p in pruebas if not p["resultado"])
    print(f"   Pruebas sin análisis numérico: {sin} (sus comentarios sí describen la prueba)")


if __name__ == "__main__":
    main()
