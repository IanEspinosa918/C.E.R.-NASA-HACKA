"""Limpia la tabla de pruebas de FLEX (PSI-69) al formato común.

Entrada:  data/raw/PSI-69_FLEX/Experimental table/PSI-69_Experimental table_FLEX.csv
Salida:   data/processed/pruebas_flex.csv
Reporte:  data/reportes/validacion_flex.csv

Lo que este script corrige o aclara (ver docs/trampas-datos.md):
  - El CSV viene en Windows-1252 y perdió los subíndices: las columnas "O", "N", "CO"
    son O2, N2 y CO2 (las 4 fracciones suman 1; "CO" llega a 0.70, sólo posible para CO2,
    que FLEX probó como supresor junto con el helio).
  - "Burning rate; mm" es la constante de quemado K en mm²/s (ley d²; rango 0.05-1.06).
  - Presión en mmHg -> atm.
  - "Test end": Extinction / Disruption / Completion. Disruption NO es extinción.
  - Valores como "~6" se guardan como 6 y se marcan como aproximados.
  - Prueba 114 trae presión 0 (imposible) y las pruebas 70 y 73 comparten identificador,
    fecha y hora con mediciones distintas: se conservan, pero quedan marcadas.

Uso:  python scripts/limpiar_flex.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun_limpieza as cl  # noqa: E402

PSI_ID = "PSI-69"
NOMBRE = "FLEX"

RESULTADO = {
    "extinction": "extincion",
    "disruption": "disrupcion",
    "completion": "combustion_completa",
}

# Columnas esperadas en el CSV original (por posición, porque los nombres traen
# caracteres perdidos). Si PSI cambia el archivo, el script avisa en lugar de
# mezclar columnas en silencio.
ESPERADAS = [
    "FLEX Test #", "FLEX Identifier", "Test Date", "Test GMT", "Fuel",
    "Ambient pressure; mmHg", "O initial", "N initial", "CO initial", "He initial",
    "Droplet initial diameter", "Visible flame extinction diameter", "Burning rate",
    "Burn time", "Test end",
]


def limpiar() -> list[dict]:
    carpeta = cl.carpeta_experimento(PSI_ID)
    archivo = next((carpeta / "Experimental table").glob("*FLEX*.csv"))
    encabezados, filas = cl.leer_csv(archivo)

    for i, esperado in enumerate(ESPERADAS):
        if i >= len(encabezados) or not encabezados[i].startswith(esperado):
            raise SystemExit(
                f"El CSV de FLEX cambió: columna {i} es '{encabezados[i] if i < len(encabezados) else '(falta)'}', "
                f"esperaba '{esperado}...'. Revisa el archivo antes de seguir."
            )

    doi = cl.doi_de(PSI_ID)
    pruebas = []
    for numero_fila, f in filas:
        f = (f + [""] * len(ESPERADAS))[: len(ESPERADAS)]
        aproximado = False

        def num(i):
            nonlocal aproximado
            valor, aprox = cl.numero(f[i])
            aproximado = aproximado or aprox
            return valor

        presion_mmhg = num(5)
        presion = cl.mmhg_a_atm(presion_mmhg)
        if presion_mmhg == 0:
            presion = 0.0  # la validación lo marca como fuera de rango y lo anula

        texto_final = f[14].strip()
        pruebas.append({
            "experimento_id": PSI_ID,
            "experimento": NOMBRE,
            "prueba_id": f"{f[0].strip()}-{f[1].strip()}",
            "fecha": cl.fecha_iso(f[2]),
            "gravedad": "microgravedad",
            "tipo_combustible": "gota",
            "combustible": f[4].strip(),
            "presion_atm": presion,
            "o2": num(6), "n2": num(7), "co2": num(8), "he": num(9),
            "flujo_aire_cm_s": None,  # FLEX: aire quieto (sin flujo forzado)
            "diametro_inicial_mm": num(10),
            "diametro_extincion_mm": num(11),
            "k_quemado_mm2_s": num(12),
            "tiempo_quemado_s": num(13),
            "resultado": RESULTADO.get(texto_final.lower(), ""),
            "resultado_original": texto_final,
            "aproximado": aproximado,
            "banderas": "",
            "notas": f"FLEX Identifier {f[1].strip()}; GMT {f[3].strip()}",
            "doi": doi,
            "archivo_origen": f"{carpeta.name}/Experimental table/{archivo.name}",
            "fila_origen": numero_fila,
        })

    # Identificadores repetidos (mismo ID, fecha y hora con mediciones distintas)
    repetidos = Counter(p["notas"] for p in pruebas)
    for p in pruebas:
        if repetidos[p["notas"]] > 1:
            p["banderas"] = ";".join(filter(None, [p["banderas"], "identificador_repetido"]))
    return pruebas


def main() -> None:
    pruebas = limpiar()
    problemas = cl.validar(pruebas)
    for p in pruebas:
        if "identificador_repetido" in p["banderas"]:
            problemas.append({
                "experimento": NOMBRE, "prueba_id": p["prueba_id"], "fila_origen": p["fila_origen"],
                "columna": "prueba_id", "valor": p["notas"], "problema": "identificador_repetido",
            })
    salida, reporte = cl.escribir("flex", pruebas, problemas)
    cl.resumen(NOMBRE, pruebas, problemas, salida, reporte)


if __name__ == "__main__":
    main()
