"""Herramientas compartidas por todos los scripts de limpieza (limpiar_*.py).

Define el FORMATO COMÚN de la tabla de pruebas (ver docs/formato-datos.md),
funciones para leer valores sucios de los CSV de PSI y la validación automática.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"
DIR_REPORTES = RAIZ / "data" / "reportes"

# ------------------------------------------------------------------ formato común

COLUMNAS = [
    "experimento_id",        # PSI-69
    "experimento",           # FLEX
    "prueba_id",             # identificador de la prueba dentro del experimento
    "fecha",                 # AAAA-MM-DD
    "gravedad",              # microgravedad | gravedad_normal
    "tipo_combustible",      # gota | gas | solido | humo
    "combustible",           # Methanol, Heptane, PMMA, SIBAL, Nomex...
    "descripcion_muestra",   # texto original de la muestra (sólidos)
    "geometria",             # gota | pelicula | placa | varilla | tela | seccion_esferica | vela
    "espesor_mm",            # mm (en varillas: diámetro)
    "ancho_mm",              # mm
    "largo_mm",              # mm (largo de la muestra sólida)
    "presion_atm",           # atm
    "o2", "n2", "co2", "he", # fracción molar (0 a 1)
    "flujo_aire_cm_s",       # cm/s (flujo inicial si hubo varios)
    "flujo_aire_min_cm_s",   # cm/s (mínimo durante la prueba)
    "flujo_aire_max_cm_s",   # cm/s (máximo durante la prueba)
    "diametro_inicial_mm",   # mm (gotas)
    "diametro_extincion_mm", # mm (gotas, llama visible)
    "k_quemado_mm2_s",       # mm²/s (constante de quemado, ley d²; llama caliente)
    "k_quemado_fria_mm2_s",  # mm²/s (constante de quemado de la llama fría)
    "diametro_extincion_fria_mm",  # mm (extinción de la llama fría; 0 = consumió la gota)
    "tiempo_quemado_s",      # s
    "longitud_quemada_mm",   # mm (sólidos: cuánto de la muestra se quemó)
    "velocidad_propagacion_mm_s",  # mm/s (sólidos: velocidad de avance de la flama)
    "resultado",             # ver RESULTADOS
    "resultado_original",    # texto tal cual venía en PSI
    "aproximado",            # si algún valor venía como "~6", rango, etc.
    "banderas",              # problemas detectados, separados por ";"
    "notas",
    "doi",
    "archivo_origen",
    "fila_origen",           # número de fila en el archivo original (1 = encabezado)
]

RESULTADOS = {
    "extincion",             # la llama se apagó antes de consumir el combustible
    "disrupcion",            # la gota se rompió/movió (NO es extinción)
    "combustion_completa",   # se consumió todo el combustible
    "no_encendio",
    "autoextincion",
    "corte_de_flujo",        # se terminó la prueba cortando el flujo
    "llama_fria",
    "encendio",              # encendió, sin más detalle
    "",                      # desconocido
}

# Rangos razonables para la validación: (mínimo, máximo)
RANGOS = {
    "presion_atm": (0.05, 5.0),
    "o2": (0.0, 1.0), "n2": (0.0, 1.0), "co2": (0.0, 1.0), "he": (0.0, 1.0),
    "flujo_aire_cm_s": (0.0, 200.0),
    "flujo_aire_min_cm_s": (0.0, 200.0),
    "flujo_aire_max_cm_s": (0.0, 200.0),
    "espesor_mm": (0.0, 50.0),
    "ancho_mm": (0.0, 1000.0),
    "largo_mm": (0.0, 2000.0),
    "longitud_quemada_mm": (0.0, 2000.0),
    "velocidad_propagacion_mm_s": (0.0, 100.0),
    "diametro_inicial_mm": (0.1, 10.0),
    "diametro_extincion_mm": (0.0, 10.0),
    "k_quemado_mm2_s": (0.0, 3.0),
    "k_quemado_fria_mm2_s": (0.0, 3.0),
    "diametro_extincion_fria_mm": (0.0, 10.0),
    "tiempo_quemado_s": (0.0, 2000.0),
}

# ------------------------------------------------------------------ lectura

VACIOS = {"", "-", "–", "—", "n/a", "na", "none", "nan", "?", "--"}


def leer_csv(ruta: Path) -> tuple[list[str], list[tuple[int, list[str]]]]:
    """Lee un CSV de PSI probando codificaciones (algunos vienen en Windows-1252).
    Regresa (encabezados, [(numero_de_fila, valores), ...]) sin filas vacías."""
    datos = ruta.read_bytes()
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = datos.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    filas = list(csv.reader(texto.splitlines()))
    encabezados = [h.strip() for h in filas[0]]
    cuerpo = [(i + 1, f) for i, f in enumerate(filas) if i > 0 and any(c.strip() for c in f)]
    return encabezados, cuerpo


def numero(valor) -> tuple[float | None, bool]:
    """Convierte un valor sucio a número. Regresa (número, es_aproximado).

    "6" -> (6, False)      "~6" -> (6, True)       "21.5 - 21.7" -> (21.6, True)
    "29 cm" -> (29, False) "–" / "" / "n/a" -> (None, False)
    """
    if valor is None:
        return None, False
    texto = str(valor).strip()
    if texto.lower() in VACIOS:
        return None, False
    aproximado = texto.startswith("~") or "approx" in texto.lower()
    texto = texto.lstrip("~").strip()
    rango = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*\D*", texto)
    if rango:
        a, b = float(rango.group(1)), float(rango.group(2))
        return (a + b) / 2, True
    encontrado = re.match(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?", texto)
    if not encontrado:
        return None, False
    return float(encontrado.group(0)), aproximado


def fecha_iso(valor: str) -> str:
    """Convierte fechas como 3/5/2009, 11/18/11 o 9-Mar-17 a AAAA-MM-DD."""
    texto = (valor or "").strip()
    for formato in ("%m/%d/%Y", "%m/%d/%y", "%d-%b-%y", "%d-%b-%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(texto, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def mmhg_a_atm(mmhg: float | None) -> float | None:
    return None if mmhg is None else mmhg / 760.0


def carpeta_experimento(psi_id: str) -> Path:
    coincidencias = sorted(DIR_RAW.glob(f"{psi_id}_*"))
    if not coincidencias:
        raise FileNotFoundError(
            f"No encuentro data/raw/{psi_id}_*/. Corre primero: python scripts/descargar_psi.py"
        )
    return coincidencias[0]


def doi_de(psi_id: str) -> str:
    try:
        ficha = json.loads((carpeta_experimento(psi_id) / "ficha.json").read_text(encoding="utf-8"))
        return ficha.get("doi", "") or ""
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


# ------------------------------------------------------------------ validación

def validar(pruebas: list[dict]) -> list[dict]:
    """Revisa rangos, composición y resultados. Agrega banderas a cada prueba
    y regresa la lista de problemas para el reporte."""
    problemas = []

    def marcar(prueba, columna, problema):
        prueba["banderas"] = ";".join(filter(None, [prueba.get("banderas", ""), problema]))
        problemas.append({
            "experimento": prueba["experimento"], "prueba_id": prueba["prueba_id"],
            "fila_origen": prueba["fila_origen"], "columna": columna,
            "valor": prueba.get(columna, ""), "problema": problema,
        })

    for p in pruebas:
        for columna, (minimo, maximo) in RANGOS.items():
            v = p.get(columna)
            if v is None or v == "":
                continue
            if not (minimo <= v <= maximo):
                marcar(p, columna, f"{columna}_fuera_de_rango")
                p[columna] = None  # un valor imposible no se usa

        gases = [p.get(g) for g in ("o2", "n2", "co2", "he")]
        if all(g is not None for g in gases):
            suma = sum(gases)
            if abs(suma - 1.0) > 0.03:
                marcar(p, "o2", f"composicion_suma_{suma:.2f}")

        # Una gota no puede apagarse más grande de lo que empezó (2 % de tolerancia de medición)
        d0, dext = p.get("diametro_inicial_mm"), p.get("diametro_extincion_mm")
        if d0 and dext and dext > d0 * 1.02:
            marcar(p, "diametro_extincion_mm", "extincion_mayor_que_diametro_inicial")

        if p.get("resultado", "") not in RESULTADOS:
            marcar(p, "resultado", "resultado_desconocido")

    return problemas


def escribir(nombre: str, pruebas: list[dict], problemas: list[dict]) -> tuple[Path, Path]:
    """Guarda data/processed/pruebas_<nombre>.csv y data/reportes/validacion_<nombre>.csv."""
    DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    DIR_REPORTES.mkdir(parents=True, exist_ok=True)

    salida = DIR_PROCESSED / f"pruebas_{nombre}.csv"
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
        w.writeheader()
        for p in pruebas:
            fila = {c: p.get(c, "") for c in COLUMNAS}
            for c, v in fila.items():
                if isinstance(v, float):
                    fila[c] = f"{v:.6g}"
                elif v is None:
                    fila[c] = ""
                elif isinstance(v, bool):
                    fila[c] = "si" if v else "no"
            w.writerow(fila)

    reporte = DIR_REPORTES / f"validacion_{nombre}.csv"
    with open(reporte, "w", newline="", encoding="utf-8-sig") as f:
        campos = ["experimento", "prueba_id", "fila_origen", "columna", "valor", "problema"]
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(problemas)

    return salida, reporte


def resumen(nombre: str, pruebas: list[dict], problemas: list[dict], salida: Path, reporte: Path) -> None:
    from collections import Counter
    print(f"\n== {nombre}: {len(pruebas)} pruebas limpias ==")
    resultados = Counter(p.get("resultado") or "(sin dato)" for p in pruebas)
    print("   Resultados:", ", ".join(f"{k}={v}" for k, v in resultados.most_common()))
    if problemas:
        tipos = Counter(p["problema"].split("_suma_")[0] for p in problemas)
        print(f"   Problemas marcados: {len(problemas)} ->", ", ".join(f"{k}={v}" for k, v in tipos.most_common()))
    print(f"   Datos:   {salida}")
    print(f"   Reporte: {reporte}")
