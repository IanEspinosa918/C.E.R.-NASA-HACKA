"""Escenarios que la IA propone probar en el simulador del tablero (IA -> simulador).

La IA agrega al final de su respuesta líneas como:

    ESCENARIO: nombre=Aire terrestre a baja presión; o2=21 %; presion=70 kPa; gravedad=1/6; flujo=10 cm/s; combustible=solido

`extraer_escenarios(texto)` quita esas líneas del texto (el usuario no las ve) y las convierte en
diccionarios con unidades fijas, que la página muestra como botones "Aplicar al simulador":

    {"nombre": "Aire terrestre a baja presión", "o2_pct": 21.0, "presion_psi": 10.15,
     "gravedad_g": 0.1667, "flujo_cm_s": 10.0, "combustible": "solido", "original": "<la línea>"}

Los parámetros que la IA no menciona van en None (= se quedan como estén en el simulador).
Aquí sólo se convierten unidades y se descartan valores imposibles; la página ajusta cada valor
al rango de sus deslizadores (así este archivo no depende de esos rangos).

Compatibilidad: si una respuesta no trae líneas ESCENARIO, el texto sale idéntico y la lista vacía.
"""

from __future__ import annotations

import re
import unicodedata

MAX_ESCENARIOS = 3
KPA_POR_PSI = 6.894757

# "ESCENARIO:", "- **Escenario:**", "SCENARIO:", "Escenario propuesto:" ... al inicio de la línea
_LINEA = re.compile(
    r"^\s*(?:[-*•]\s*)?(?:\*\*|__|`)?\s*(?:escenario|scenario)(?:\s+(?:propuesto|sugerido|proposed|suggested))?"
    r"\s*(?:\d+\s*)?(?:\*\*|__)?\s*[:：]\s*(?:\*\*|__)?\s*(.+?)[\s`]*$", re.IGNORECASE)

# Encabezado que a veces la IA pone antes de las líneas ("Escenarios para el simulador:")
_ENCABEZADO = re.compile(
    r"^\s*(?:[-*•#]+\s*)?(?:\*\*|__)?[^.\n]{0,50}(escenarios?|scenarios?|simulador|simulator)[^.\n]{0,40}[:：]\s*(?:\*\*|__)?\s*$",
    re.IGNORECASE)

_NUMERO = r"[-+]?\d+(?:[.,]\d+)?"


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _clave(texto: str) -> str | None:
    t = re.sub(r"[\s_\-*`]", "", _sin_acentos(texto.lower()).replace("₂", "2"))
    if t in ("nombre", "name", "titulo", "title", "etiqueta", "label"):
        return "nombre"
    if t in ("o2", "oxigeno", "oxygen", "%o2", "o2%", "concentraciono2", "concentraciondeoxigeno"):
        return "o2"
    if t in ("presion", "pressure", "p", "presiontotal", "presioncabina", "totalpressure", "cabinpressure"):
        return "presion"
    if t in ("gravedad", "gravity", "g"):
        return "gravedad"
    if t in ("flujo", "flow", "flujodeaire", "airflow", "ventilacion", "ventilation", "velocidad", "aire"):
        return "flujo"
    if t in ("combustible", "fuel", "material"):
        return "combustible"
    return None


def _numero(texto: str) -> float | None:
    m = re.search(_NUMERO, texto)
    return float(m.group(0).replace(",", ".")) if m else None


def oxigeno(valor: str) -> float | None:
    """'21 %', '21', '0.21' -> 21.0 (porcentaje de O₂)."""
    n = _numero(valor)
    if n is None:
        return None
    if n <= 1 and "%" not in valor:
        n *= 100  # escrito como fracción
    return round(n, 2) if 0 < n <= 100 else None


def presion_psi(valor: str) -> float | None:
    """'70 kPa', '10.2 psi', '1 atm', '1.013 bar' -> psi. Sin unidad: >= 30 se toma como kPa."""
    n = _numero(valor)
    if n is None or n <= 0:
        return None
    unidad = _sin_acentos(valor.lower())
    if "kpa" in unidad:
        psi = n / KPA_POR_PSI
    elif "hpa" in unidad or "mbar" in unidad:
        psi = n / (KPA_POR_PSI * 10)
    elif "atm" in unidad:
        psi = n * 14.6959
    elif "bar" in unidad:
        psi = n * 14.5038
    elif "psi" in unidad:
        psi = n
    else:
        psi = n / KPA_POR_PSI if n >= 30 else n
    return round(psi, 2) if 0 < psi <= 60 else None


def gravedad(valor: str) -> float | None:
    """'1/6', '3/8 g', '0', '0.38 g', '1.62 m/s²', 'Luna', 'Marte', 'órbita', 'Tierra' -> fracción de g."""
    t = _sin_acentos(valor.lower())
    palabras = [(r"\b(luna|lunar|moon)\b", 1 / 6), (r"\b(marte|marciana?|mars|martian)\b", 3 / 8),
                (r"\b(orbita|orbit|orbital|iss|eei|microgravedad|microgravity|ingravidez)\b", 0.0),
                (r"\b(tierra|terrestre|earth)\b", 1.0)]
    if not re.search(r"\d", t):
        for patron, g in palabras:
            if re.search(patron, t):
                return round(g, 4)
        return None
    fraccion = re.search(r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)", t)
    if fraccion and float(fraccion.group(2).replace(",", ".")) > 0:
        g = float(fraccion.group(1).replace(",", ".")) / float(fraccion.group(2).replace(",", "."))
    else:
        n = _numero(t)
        if n is None:
            return None
        g = n / 9.80665 if re.search(r"m\s*/\s*s", t) else n
    return round(g, 4) if 0 <= g <= 10 else None


def flujo_cm_s(valor: str) -> float | None:
    """'10 cm/s', '0.1 m/s', '5 mm/s', '10' -> cm/s."""
    n = _numero(valor)
    if n is None or n < 0:
        return None
    t = valor.lower().replace(" ", "")
    if "mm/s" in t:
        n /= 10
    elif "cm/s" not in t and re.search(r"(?<![a-z])m/s", t):
        n *= 100
    return round(n, 2) if n <= 1000 else None


def combustible(valor: str) -> str | None:
    t = _sin_acentos(valor.lower())
    if re.search(r"solid|polimer|polymer|tela|fabric|cable|pmma|nomex|algodon|cotton|acril", t):
        return "solido"
    if re.search(r"liquid|gota|droplet|heptano|heptane|decano|decane|alcohol|etanol|ethanol", t):
        return "liquido"
    if re.search(r"\bgas|metano|methane|etileno|ethylene|propano|propane", t):
        return "gas"
    return None


def _nombre(valor: str) -> str | None:
    nombre = re.sub(r"[*_`#]+", "", valor).strip(" .;:-\"'")[:80].strip()
    if not nombre:
        return None
    try:  # un nombre no puede afirmar que el escenario es seguro o no inflamable
        from llm import VEREDICTO
        if VEREDICTO.search(nombre):
            return None
    except ImportError:
        pass
    return nombre


def leer_linea(contenido: str) -> dict | None:
    """Convierte 'o2=21 %; presion=70 kPa; ...' en un escenario. None si no trae ningún parámetro."""
    escenario = {"nombre": None, "o2_pct": None, "presion_psi": None, "gravedad_g": None,
                 "flujo_cm_s": None, "combustible": None}
    for pedazo in re.split(r"\s*[;|]\s*", contenido):
        if "=" not in pedazo:
            continue
        clave, valor = (s.strip() for s in pedazo.split("=", 1))
        clave = _clave(clave)
        if not clave or not valor:
            continue
        if clave == "nombre":
            escenario["nombre"] = _nombre(valor)
        elif clave == "o2":
            escenario["o2_pct"] = oxigeno(valor)
        elif clave == "presion":
            escenario["presion_psi"] = presion_psi(valor)
        elif clave == "gravedad":
            escenario["gravedad_g"] = gravedad(valor)
        elif clave == "flujo":
            escenario["flujo_cm_s"] = flujo_cm_s(valor)
        elif clave == "combustible":
            escenario["combustible"] = combustible(valor)
    parametros = [k for k in escenario if k != "nombre" and escenario[k] is not None]
    return escenario if parametros else None


def extraer_escenarios(texto: str) -> tuple[str, list[dict]]:
    """Quita del texto las líneas ESCENARIO y las regresa como escenarios (máximo 3, sin repetidos).
    Una línea que empieza con "Escenario:" pero no trae parámetros (clave=valor) se deja en el texto."""
    lineas = texto.split("\n")
    escenarios: list[dict] = []
    quitar: set[int] = set()
    for i, linea in enumerate(lineas):
        m = _LINEA.match(linea)
        if not m:
            continue
        escenario = leer_linea(m.group(1))
        if escenario is None:
            continue
        quitar.add(i)
        clave = tuple(escenario[k] for k in ("o2_pct", "presion_psi", "gravedad_g", "flujo_cm_s", "combustible"))
        if len(escenarios) < MAX_ESCENARIOS and all(
                tuple(e[k] for k in ("o2_pct", "presion_psi", "gravedad_g", "flujo_cm_s", "combustible")) != clave
                for e in escenarios):
            escenarios.append({**escenario, "original": m.group(1).strip()[:300]})
    if not quitar:
        return texto, []
    # Encabezado suelto justo antes de las líneas ("Escenarios para probar en el simulador:")
    primera = min(quitar)
    anterior = primera - 1
    while anterior >= 0 and not lineas[anterior].strip():
        anterior -= 1
    if anterior >= 0 and _ENCABEZADO.match(lineas[anterior]):
        quitar.add(anterior)
    restantes = [l for i, l in enumerate(lineas) if i not in quitar]
    limpio = re.sub(r"\n{3,}", "\n\n", "\n".join(restantes)).strip()
    return limpio, escenarios


def describir(escenario: dict, idioma: str = "es") -> str:
    """Texto corto para la terminal: 'O₂ 21 % · 10.15 psi (70 kPa) · 1/6 g · 10 cm/s · sólidos'."""
    ingles = idioma == "en"
    partes = []
    if escenario.get("o2_pct") is not None:
        partes.append(f"O₂ {escenario['o2_pct']:g} %")
    if escenario.get("presion_psi") is not None:
        partes.append(f"{escenario['presion_psi']:g} psi ({escenario['presion_psi'] * KPA_POR_PSI:.0f} kPa)")
    if escenario.get("gravedad_g") is not None:
        partes.append(f"{escenario['gravedad_g']:.3g} g")
    if escenario.get("flujo_cm_s") is not None:
        partes.append(f"{escenario['flujo_cm_s']:g} cm/s")
    if escenario.get("combustible"):
        nombres = ({"solido": "solids", "liquido": "liquids", "gas": "gases"} if ingles else
                   {"solido": "sólidos", "liquido": "líquidos", "gas": "gases"})
        partes.append(nombres[escenario["combustible"]])
    return " · ".join(partes)
