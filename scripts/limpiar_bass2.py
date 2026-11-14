"""Limpia la tabla de pruebas de BASS-II (PSI-25) al formato común.

BASS-II quemó materiales sólidos (PMMA en película, placa y varilla; tela SIBAL;
Nomex; una vela) en la ISS, con flujo de aire forzado y oxígeno entre ~14 % y 22 %.

Entrada:  data/raw/PSI-25_BASS-II/Experimental table/PSI-25_Experimental table_BASS-II.csv
          (mismo contenido que Science Documents/..._Test.Matrices.xlsx, en una sola tabla)
Salida:   data/processed/pruebas_bass2.csv
Reporte:  data/reportes/validacion_bass2.csv

Según el ReadMe de BASS-II (Science Documents/..._BASS-II_ReadMe.docx):
  - "Air display" = velocidad del aire en el ducto, en cm/s (respuesta lenta, ~1 min).
  - "Fan display" = voltaje del ventilador x10 (NO es velocidad).
  - Durante una prueba se cambiaba el flujo varias veces: "5 3 2 1 ext" = se bajó el
    flujo hasta que la flama se apagó. Guardamos flujo inicial, mínimo y máximo.
  - El oxígeno está "calibrado" con un ajuste constante por día (sensor descalibrado).
  - La fecha del video es un día después de la fecha real (error de año bisiesto).

Trampas que resuelve:
  - En el CSV se perdieron las comas: "10, 5, 3" aparece como "10   5   3".
  - Valores de perilla del ventilador mezclados ("pots 0.4 0.36", "(0.36)"): se ignoran.
  - El resultado NO tiene columna propia; se deduce sólo cuando el texto lo dice
    ("ext", "blowoff", "no ign", "would not stay lit"). Si no lo dice, queda vacío.
  - Tres pruebas terminan con O2 cercano a 1 %: se marcan como "o2_final_anomalo".

Uso:  python scripts/limpiar_bass2.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun_limpieza as cl  # noqa: E402

PSI_ID = "PSI-25"
NOMBRE = "BASS-II"
PULGADA_MM = 25.4

ESPERADAS = [
    "PI", "Test #", "Date", "GMT", "Sample #", "Fuel Sample Material", "Flow restrictor",
    "Fan display", "Air display", "Radiometer gain", "Total Frames Shot",
    "Calibrated  initial O2", "Calibrated final O2", "Initial CO2", "Final CO2",
    "Initial CO", "Final CO",
]


# ------------------------------------------------------------------ muestra

def interpretar_muestra(texto: str) -> dict:
    """'1/4" clear rod' -> PMMA, varilla, 6.35 mm;  '2 cm 100 micron thick PMMA' -> película..."""
    t = texto.lower().replace("blac ", "black ").replace("2ide", "wide")
    info = {"combustible": "", "geometria": "", "espesor_mm": None, "ancho_mm": None, "notas": []}

    if "sibal" in t:
        info.update(combustible="SIBAL (75% algodón / 25% fibra de vidrio)", geometria="tela")
    elif "nomex" in t:
        info.update(combustible="Nomex III", geometria="tela")
    elif "candle" in t or "wax" in t:
        info.update(combustible="Cera (vela)", geometria="vela")
    elif "spherical" in t:
        info.update(combustible="PMMA", geometria="seccion_esferica")
    elif "rod" in t:
        info.update(combustible="PMMA", geometria="varilla")
        m = re.search(r'(\d+)\s*/\s*(\d+)\s*"?', t) or re.search(r'(\d*\.\d+|\d+)\s*"', t)
        if m:
            pulgadas = int(m.group(1)) / int(m.group(2)) if m.lastindex == 2 else float(m.group(1))
            info["espesor_mm"] = round(pulgadas * PULGADA_MM, 3)  # diámetro
        if "black" in t:
            info["notas"].append("varilla negra")
        elif "clear" in t:
            info["notas"].append("varilla transparente")
    else:  # películas y placas de PMMA
        info["combustible"] = "PMMA"
        micras = re.search(r"(\d+)\s*micron", t)
        mm = re.search(r"(\d*\.?\d+)\s*mm", t)
        if micras:
            info["espesor_mm"] = int(micras.group(1)) / 1000
        elif mm:
            info["espesor_mm"] = float(mm.group(1))
        info["geometria"] = "pelicula" if ("film" in t or (info["espesor_mm"] or 1) < 0.5) else "placa"

    ancho = re.search(r"(\d+)\s*cm", t)
    if ancho and info["geometria"] not in ("varilla", "seccion_esferica"):
        info["ancho_mm"] = int(ancho.group(1)) * 10
    elif ancho and info["geometria"] == "seccion_esferica":
        info["espesor_mm"] = int(ancho.group(1)) * 10  # diámetro de la sección esférica
    if "1 sided" in t:
        info["notas"].append("quemado por 1 lado")
    if "2 sided" in t:
        info["notas"].append("quemado por 2 lados")
    if "moved igniter" in t or "top side ign" in t:
        info["notas"].append("ignición modificada")
    return info


# ------------------------------------------------------------------ flujo y resultado

def interpretar_flujo(texto: str) -> dict:
    """'5  3  2  1 ext' -> inicial 5, mínimo 1, máximo 5, resultado extinción."""
    original = texto.strip()
    t = original.lower()
    info = {"inicial": None, "minimo": None, "maximo": None, "resultado": "", "aproximado": False,
            "detalle": ""}

    if "no ign" in t:
        info["resultado"] = "no_encendio"
    elif "would not stay lit" in t:
        info["resultado"] = "autoextincion"
    elif "blowoff" in t:
        info["resultado"], info["detalle"] = "extincion", "extinción por soplado (flujo alto)"
    elif "ext" in t:
        info["resultado"], info["detalle"] = "extincion", "extinción al bajar el flujo"
    elif re.search(r"\bign\b", t):
        info["resultado"] = "encendio"

    def numeros(texto: str) -> list[float]:
        salida = []
        for token in re.findall(r"<\s*\d*\.?\d+|\d*\.?\d+", texto):
            if token.startswith("<"):
                salida.append(float(token[1:].strip()) / 2)  # "<1" -> 0.5 aproximado
                info["aproximado"] = True
            else:
                salida.append(float(token))
        return salida

    # Quitar lo que NO es velocidad del aire: valores de perilla ("pot") y paréntesis
    sin_max = re.sub(r"max\s*\(?\d+\)?", "max", t)
    # "0.5 pot": valor de perilla ANTES de la palabra pot (las perillas van de 0 a ~1)
    sin_pot = re.sub(r"(?<![\d.])(\d*\.\d+|0)\s*pots?\b", " ", sin_max)
    # "pots 0.4 0.36 ...": todo lo que sigue a la palabra pot son valores de perilla
    sin_pot = re.split(r"\bpots?\b", sin_pot)[0]
    dentro = " ".join(re.findall(r"\(([^)]*)\)", sin_pot))
    fuera = re.sub(r"\([^)]*\)", " ", sin_pot)
    if "cm/s" in fuera:
        fuera = fuera.split("cm/s")[0].split()[-1]  # '49 5 cm/s' -> '5'

    valores = numeros(fuera)
    valores_dentro = numeros(dentro) if "pot" not in dentro else []
    # BASS llegaba a ~40 cm/s. Si lo de fuera pasa de 40 y lo de dentro no, lo de fuera
    # es el ventilador y la velocidad está entre paréntesis: '49 44 42 (5 2 0)'.
    if valores and max(valores) > 40 and valores_dentro and max(valores_dentro) <= 40:
        valores = valores_dentro
    if valores and max(valores) > 40:
        info["sospechoso"] = True
    if "?" in t or "~" in t or re.search(r"\blow(er)?\b", t) or "etc" in t:
        info["aproximado"] = True
    if valores:
        info["inicial"], info["minimo"], info["maximo"] = valores[0], min(valores), max(valores)
    # "down to ext", "very low", "pots ... off": el flujo bajó por debajo del último valor
    # escrito, pero no se registró cuánto. Mejor dejar el mínimo vacío que inventarlo.
    perillas_dentro = [v for v in numeros(dentro)] if dentro else []
    bajo_con_perilla = len(perillas_dentro) > 1 and max(perillas_dentro) <= 1.5
    if re.search(r"down|decr|\blow(er)?\b|\boff\b|\bpot", t) or bajo_con_perilla:
        info["minimo"] = None
        info["aproximado"] = True
        info["detalle"] = "; ".join(filter(None, [
            info["detalle"], "el flujo bajó por debajo del último valor registrado (mínimo no anotado)"]))
    return info


def limpiar() -> list[dict]:
    carpeta = cl.carpeta_experimento(PSI_ID)
    archivo = next((carpeta / "Experimental table").glob("*BASS-II*.csv"))
    encabezados, filas = cl.leer_csv(archivo)
    for i, esperado in enumerate(ESPERADAS):
        if i >= len(encabezados) or not encabezados[i].startswith(esperado):
            raise SystemExit(
                f"El CSV de BASS-II cambió: columna {i} es "
                f"'{encabezados[i] if i < len(encabezados) else '(falta)'}', esperaba '{esperado}...'."
            )

    doi = cl.doi_de(PSI_ID)
    pruebas = []
    for numero_fila, f in filas:
        f = (f + [""] * len(ESPERADAS))[: len(ESPERADAS)]
        muestra = interpretar_muestra(f[5])
        flujo = interpretar_flujo(f[8])
        o2_ini, a1 = cl.numero(f[11])
        o2_fin, a2 = cl.numero(f[12])
        co2_ini, a3 = cl.numero(f[13])
        banderas = []
        if o2_fin is not None and o2_fin < 5:
            banderas.append("o2_final_anomalo")
        if not flujo["resultado"]:
            banderas.append("resultado_no_registrado_en_tabla")
        if flujo.get("sospechoso"):
            banderas.append("flujo_mayor_a_40_revisar")

        notas = [f"Investigador: {f[0].strip()}", f"Restrictor de flujo: {f[6].strip()}",
                 f"Fan display (voltaje x10): {f[7].strip()}",
                 f"O2 final: {f[12].strip()} %", f"CO inicial/final: {f[15].strip()}/{f[16].strip()} ppm"]
        if flujo["detalle"]:
            notas.append(flujo["detalle"])
        notas.extend(muestra["notas"])

        pruebas.append({
            "experimento_id": PSI_ID,
            "experimento": NOMBRE,
            "prueba_id": f[1].strip(),
            "fecha": cl.fecha_iso(f[2]),
            "gravedad": "microgravedad",
            "tipo_combustible": "solido",
            "combustible": muestra["combustible"],
            "descripcion_muestra": " ".join(f[5].split()),
            "geometria": muestra["geometria"],
            "espesor_mm": muestra["espesor_mm"],
            "ancho_mm": muestra["ancho_mm"],
            "presion_atm": None,  # no viene en la tabla (cabina de la ISS, ~1 atm)
            "o2": None if o2_ini is None else o2_ini / 100,
            "n2": None, "he": None,
            "co2": None if co2_ini is None else co2_ini / 100,
            "flujo_aire_cm_s": flujo["inicial"],
            "flujo_aire_min_cm_s": flujo["minimo"],
            "flujo_aire_max_cm_s": flujo["maximo"],
            "diametro_inicial_mm": None, "diametro_extincion_mm": None,
            "k_quemado_mm2_s": None, "tiempo_quemado_s": None,
            "resultado": flujo["resultado"],
            "resultado_original": " ".join(f[8].split()),
            "aproximado": flujo["aproximado"] or a1 or a2 or a3,
            "banderas": ";".join(banderas),
            "notas": "; ".join(notas),
            "doi": doi,
            "archivo_origen": f"{carpeta.name}/Experimental table/{archivo.name}",
            "fila_origen": numero_fila,
        })
    return pruebas


def main() -> None:
    pruebas = limpiar()
    problemas = cl.validar(pruebas)
    for p in pruebas:
        if "o2_final_anomalo" in p["banderas"]:
            problemas.append({
                "experimento": NOMBRE, "prueba_id": p["prueba_id"], "fila_origen": p["fila_origen"],
                "columna": "o2", "valor": p["notas"], "problema": "o2_final_anomalo",
            })
    salida, reporte = cl.escribir("bass2", pruebas, problemas)
    cl.resumen(NOMBRE, pruebas, problemas, salida, reporte)
    materiales = Counter(f"{p['combustible'].split(' (')[0]} {p['geometria']}" for p in pruebas)
    print("   Materiales:", ", ".join(f"{k}={v}" for k, v in materiales.most_common()))
    sin = sum(1 for p in pruebas if not p["resultado"])
    print(f"   Pruebas sin resultado escrito en la tabla: {sin} (ver videos/publicaciones)")


if __name__ == "__main__":
    main()
