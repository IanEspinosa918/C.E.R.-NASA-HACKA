"""Limpia las pruebas de Saffire I, II y III (PSI-98, PSI-99, PSI-100) al formato común.

Saffire (Spacecraft Fire Experiment) quemó materiales dentro de la nave de carga Cygnus
después de desacoplarse de la ISS (no dentro de la estación):
  - Saffire I y III: una muestra GRANDE de tela SIBAL (94 x 40.6 cm), con flujo de 20 y
    30 cm/s. Objetivo: ver qué tan rápido crece un incendio grande en microgravedad.
  - Saffire II: 9 muestras pequeñas (5 x 29 cm), del mismo tamaño que la prueba estándar
    de la NASA en la Tierra (NASA-STD-6001 Test 1). Para cada muestra trae el resultado en
    MICROGRAVEDAD y en GRAVEDAD NORMAL -> aquí se guardan como DOS filas por muestra.

Entrada:  data/raw/PSI-98_SAFFIRE-I/Experimental table/*.csv
          data/raw/PSI-99_SAFFIRE-II/Experimental table/*.csv
          data/raw/PSI-100_SAFFIRE-III/Experimental table/*.csv
Salida:   data/processed/pruebas_saffire.csv
Reporte:  data/reportes/validacion_saffire.csv

Trampas que resuelve (ver docs/trampas-datos.md):
  - Unidades dentro de las celdas ("29 cm", "80 W", "9.2 s", "20 cm/s").
  - "037 mm" = 0.37 mm (falta el punto decimal).
  - Muestras 2-6 y 2-9 sin material: es el mismo de la fila de arriba (celda combinada).
  - Filas F1/F2 no son pruebas (visualización del flujo antes y después): se omiten.
  - "Complete" = se quemó toda la muestra; "Acceleratory" = la flama se fue acelerando.
  - Notas 1-4 al pie de la tabla con información clave: se copian a cada prueba.
  - Saffire I reporta la tela SIBAL con 0.37 cm de espesor y Saffire II con 0.37 mm:
    posible error de unidades, se marca. En Saffire I largo y ancho vienen invertidos.

Uso:  python scripts/limpiar_saffire.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun_limpieza as cl  # noqa: E402

NOTAS_SAFFIRE2 = {
    "note 1": "O2 derivado del CO2 medido, referido al O2 inicial reportado por la ISS",
    "note 2": "la parte de PMMA se consumió por completo, pero el Nomex no encendió",
    "note 3": "longitud de combustible con daño visible significativo",
    "note 4": "las flamas quedaron ancladas en la base de la muestra, con regresión muy lenta (0.01 a 0.04 mm/s)",
}


def longitud_mm(texto: str) -> tuple[float | None, bool]:
    """'29 cm' -> 290; '0.27 mm' -> 0.27; '037 mm' -> 0.37; '~ 10 cm (note 3)' -> 100 aprox."""
    t = (texto or "").strip().lower()
    t = re.sub(r"\(.*?\)", "", t).strip()
    if not t or t in cl.VACIOS or t.startswith("see"):
        return None, False
    aprox = "~" in t
    t = t.replace("~", "").strip()
    sin_punto = re.fullmatch(r"0(\d+)\s*(mm|cm)", t)  # "037 mm" -> "0.37 mm"
    if sin_punto:
        t = f"0.{sin_punto.group(1)} {sin_punto.group(2)}"
    valor, a = cl.numero(t)
    if valor is None:
        return None, False
    if "cm" in t:
        valor *= 10
    return round(valor, 4), aprox or a


def oxigeno(texto: str) -> tuple[float | None, bool]:
    t = (texto or "").replace(" to ", " - ")
    valor, aprox = cl.numero(t)
    return (None if valor is None else valor / 100), aprox


def notas_de(*textos: str) -> list[str]:
    salida = []
    for t in textos:
        for clave, texto in NOTAS_SAFFIRE2.items():
            if clave in (t or "").lower() and texto not in salida:
                salida.append(texto)
    return salida


def base(psi_id: str, nombre: str, carpeta: Path, archivo: Path, fila: int) -> dict:
    return {
        "experimento_id": psi_id, "experimento": nombre, "tipo_combustible": "solido",
        "doi": cl.doi_de(psi_id), "fila_origen": fila, "banderas": "", "aproximado": False,
        "archivo_origen": f"{carpeta.name}/Experimental table/{archivo.name}",
    }


# ------------------------------------------------------------------ Saffire I y III

def saffire_grande(psi_id: str, nombre: str) -> list[dict]:
    carpeta = cl.carpeta_experimento(psi_id)
    archivo = next((carpeta / "Experimental table").glob("*.csv"))
    encabezados, filas = cl.leer_csv(archivo)
    col = {h.lower().strip(): i for i, h in enumerate(encabezados)}

    def campo(f, nombre_col):
        for clave, i in col.items():
            if clave.startswith(nombre_col):
                return f[i].strip() if i < len(f) else ""
        return ""

    pruebas = []
    for numero_fila, f in filas:
        muestra = campo(f, "sample number")
        if not re.fullmatch(r"S\d+", muestra):
            continue  # F1/F2: visualización del flujo, no son pruebas
        p = base(psi_id, nombre, carpeta, archivo, numero_fila)

        espesor, _ = longitud_mm(campo(f, "sample thickness") + ("" if "cm" in campo(f, "sample thickness") else " cm"))
        largo, _ = longitud_mm(campo(f, "sample length") + ("" if "cm" in campo(f, "sample length") else " cm"))
        ancho, _ = longitud_mm(campo(f, "sample width") + ("" if "cm" in campo(f, "sample width") else " cm"))
        notas = ["muestra grande; quemada en la nave Cygnus tras desacoplarse de la ISS"]
        if largo and ancho and largo < ancho:  # Saffire I trae largo y ancho invertidos
            largo, ancho = ancho, largo
            notas.append("largo y ancho venían invertidos en la tabla original")
        banderas = ["espesor_unidad_dudosa"]  # SIBAL: 0.3x cm aquí vs 0.37 mm en Saffire II
        notas.append("espesor reportado en cm; Saffire II reporta la misma tela en mm (posible error de unidades)")

        o2, aprox_o2 = oxigeno(campo(f, "percent o2"))
        tiempo, _ = cl.numero(campo(f, "burn time"))
        direccion = campo(f, "flow direction") or campo(f, "direction")
        potencia = campo(f, "ignition power")
        if potencia:
            notas.append(f"ignición: {potencia} W por {campo(f, 'ignition time')} s")
        notas.append(f"flujo {'concurrente (en el mismo sentido que la flama)' if 'conc' in direccion.lower() else 'opuesto a la flama'}")

        p.update({
            "prueba_id": muestra, "gravedad": "microgravedad",
            "combustible": "SIBAL (75% algodón / 25% fibra de vidrio)",
            "descripcion_muestra": campo(f, "material"), "geometria": "tela",
            "espesor_mm": espesor, "ancho_mm": ancho, "largo_mm": largo,
            "o2": o2, "flujo_aire_cm_s": cl.numero(campo(f, "air flow"))[0],
            "tiempo_quemado_s": tiempo,
            "resultado": "encendio" if tiempo else "",
            "resultado_original": f"Burn time: {campo(f, 'burn time') or '(sin dato)'}",
            "aproximado": aprox_o2, "banderas": ";".join(banderas + ([] if tiempo else ["resultado_no_registrado_en_tabla"])),
            "notas": "; ".join(notas),
        })
        pruebas.append(p)
    return pruebas


# ------------------------------------------------------------------ Saffire II

MATERIALES_S2 = {
    "silicone": ("Silicona", "lamina"),
    "cotton-fiberglass (sibal)": ("SIBAL (75% algodón / 25% fibra de vidrio)", "tela"),
    "pmma & nomex": ("PMMA + Nomex", "compuesta"),
    "pmma": ("PMMA", "placa"),
}


def resultado_s2(longitud_texto: str, largo_muestra: float | None, tiempo_texto: str) -> tuple[str, float | None, bool]:
    """Interpreta '~ 0', '29 cm', 'Complete', '7.6 cm', '5 cm & 0 (note 2)'."""
    t = (longitud_texto or "").strip().lower()
    if not t or t in cl.VACIOS:
        return "", None, False
    if t.startswith("complete"):
        return "combustion_completa", largo_muestra, False
    if "&" in t:  # PMMA + Nomex: la parte de PMMA se quemó, el Nomex no encendió
        valor, aprox = longitud_mm(t.split("&")[0])
        return "encendio", valor, True
    valor, aprox = longitud_mm(t)
    if valor is None:
        return "", None, False
    if valor == 0:
        return "autoextincion", 0.0, aprox  # encendió pero no se propagó
    if largo_muestra and valor >= largo_muestra * 0.98:
        return "combustion_completa", valor, aprox
    if "note 3" in t or "note 4" in t:
        return "encendio", valor, aprox  # flama anclada, quemó sólo una parte
    return "autoextincion", valor, aprox     # se propagó un tramo y se apagó


def velocidad(texto: str) -> tuple[float | None, str]:
    t = (texto or "").strip().lower()
    if t.startswith("acceler"):
        return None, "propagación aceleratoria (la flama se fue acelerando)"
    if "note 4" in t:
        return None, ""
    valor, _ = cl.numero(t) if "mm/s" in t else (None, False)
    return valor, ""


def saffire2() -> list[dict]:
    psi_id, nombre = "PSI-99", "SAFFIRE-II"
    carpeta = cl.carpeta_experimento(psi_id)
    archivo = next((carpeta / "Experimental table").glob("*.csv"))
    encabezados, filas = cl.leer_csv(archivo)
    if len(encabezados) < 15 or not encabezados[11].endswith("-g Burn Length") or encabezados[13] != "1-g Burn Length":
        raise SystemExit("El CSV de Saffire II cambió de columnas. Revísalo antes de seguir.")

    pruebas, material_anterior = [], ""
    for numero_fila, f in filas:
        f = (f + [""] * 17)[:17]
        muestra = f[0].strip()
        if not re.fullmatch(r"2-\d+", muestra):
            continue  # F1/F2 y notas al pie
        material_texto = f[1].strip() or material_anterior  # celda combinada en el original
        heredado = not f[1].strip()
        material_anterior = material_texto
        combustible, geometria = MATERIALES_S2.get(material_texto.lower(), (material_texto, ""))

        espesor, aprox_e = longitud_mm(f[2]) if " and " not in f[2] else (None, False)
        largo, _ = longitud_mm(f[3])
        ancho, _ = longitud_mm(f[4])
        o2, aprox_o2 = oxigeno(f[6])
        tiempo, _ = cl.numero(f[9])
        direccion = f[10].strip().lower()

        comunes = [f"ignición: {f[7].strip()} por {f[8].strip()}",
                   f"flujo {'concurrente' if 'conc' in direccion else 'opuesto'}"]
        if heredado:
            comunes.append("material tomado de la fila anterior (celda combinada en el original)")
        if re.fullmatch(r"0\d+\s*mm", f[2].strip()):
            comunes.append(f"espesor corregido: '{f[2].strip()}' = {espesor} mm (faltaba el punto decimal)")
        if " and " in f[2] or f[2].lower().startswith("see"):
            comunes.append(f"espesor: {f[2].strip()}")
        if " and " in f[3]:
            comunes.append(f"largo: {f[3].strip()}")
        comunes.extend(notas_de(f[6]))

        # --- fila de microgravedad (en la nave Cygnus)
        res_mg, long_mg, aprox_mg = resultado_s2(f[11], largo, f[9])
        vel_mg, nota_vel_mg = velocidad(f[12])
        p = base(psi_id, nombre, carpeta, archivo, numero_fila)
        p.update({
            "prueba_id": f"{muestra}-microg", "gravedad": "microgravedad",
            "combustible": combustible, "descripcion_muestra": material_texto, "geometria": geometria,
            "espesor_mm": espesor, "ancho_mm": ancho, "largo_mm": largo if " and " not in f[3] else None,
            "o2": o2, "flujo_aire_cm_s": cl.numero(f[5])[0],
            "tiempo_quemado_s": tiempo,
            "longitud_quemada_mm": long_mg, "velocidad_propagacion_mm_s": vel_mg,
            "resultado": res_mg,
            "resultado_original": f"µg burn length: {f[11].strip()}; µg spread: {f[12].strip()}; burn time: {f[9].strip()}",
            "aproximado": aprox_mg or aprox_o2 or aprox_e,
            "notas": "; ".join(comunes + [n for n in [nota_vel_mg] if n] + notas_de(f[11], f[12])
                               + (["tiempo de quemado insignificante"] if f[9].strip().lower() == "insignificant" else [])),
        })
        pruebas.append(p)

        # --- fila de gravedad normal (prueba en la Tierra, mismo tamaño de muestra)
        res_1g, long_1g, aprox_1g = resultado_s2(f[13], largo, "")
        vel_1g, nota_vel_1g = velocidad(f[14])
        q = base(psi_id, nombre, carpeta, archivo, numero_fila)
        q.update({
            "prueba_id": f"{muestra}-1g", "gravedad": "gravedad_normal",
            "combustible": combustible, "descripcion_muestra": material_texto, "geometria": geometria,
            "espesor_mm": espesor, "ancho_mm": ancho, "largo_mm": largo if " and " not in f[3] else None,
            "o2": None, "flujo_aire_cm_s": None,
            "longitud_quemada_mm": long_1g, "velocidad_propagacion_mm_s": vel_1g,
            "resultado": res_1g,
            "resultado_original": f"1-g burn length: {f[13].strip()}; 1-g spread rate: {f[14].strip()}",
            "aproximado": aprox_1g,
            "notas": "; ".join(["prueba en tierra con el mismo tamaño de muestra que la prueba "
                                "estándar NASA-STD-6001 Test 1 (según el ReadMe)"]
                               + comunes[1:] + [n for n in [nota_vel_1g] if n] + notas_de(f[13], f[14])),
        })
        pruebas.append(q)
    return pruebas


def main() -> None:
    pruebas = saffire_grande("PSI-98", "SAFFIRE-I") + saffire2() + saffire_grande("PSI-100", "SAFFIRE-III")
    problemas = cl.validar(pruebas)
    for p in pruebas:
        if "espesor_unidad_dudosa" in p["banderas"]:
            problemas.append({"experimento": p["experimento"], "prueba_id": p["prueba_id"],
                              "fila_origen": p["fila_origen"], "columna": "espesor_mm",
                              "valor": p["espesor_mm"], "problema": "espesor_unidad_dudosa"})
    salida, reporte = cl.escribir("saffire", pruebas, problemas)
    cl.resumen("SAFFIRE I/II/III", pruebas, problemas, salida, reporte)
    print("   Comparación Saffire II (microgravedad vs. gravedad normal):")
    s2 = {}
    for p in pruebas:
        if p["experimento"] == "SAFFIRE-II":
            s2.setdefault(p["prueba_id"].rsplit("-", 1)[0], {})[p["gravedad"]] = p
    for muestra, g in s2.items():
        mg, ng = g.get("microgravedad", {}), g.get("gravedad_normal", {})
        print(f"     {muestra} {mg.get('combustible','')[:14]:14} µg: {mg.get('resultado') or '?':20} 1g: {ng.get('resultado') or '?'}")


if __name__ == "__main__":
    main()
