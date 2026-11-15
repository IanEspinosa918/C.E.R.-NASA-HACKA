"""Glosario español -> inglés para la búsqueda por palabras clave.

Los documentos de PSI están en inglés. La búsqueda por significado (vectores) cruza idiomas,
pero la búsqueda por palabras no: "llamas frías" nunca coincide con "cool flame". Este
glosario traduce los términos técnicos de la pregunta para que la búsqueda por palabras
también funcione con preguntas en español. Agrega términos aquí cuando hagan falta.
"""

from __future__ import annotations

import re
import unicodedata

# Frases primero (más largas), luego palabras sueltas. Las claves van sin acentos y en minúsculas.
GLOSARIO: dict[str, list[str]] = {
    # fenómenos de llama
    "llamas frias": ['"cool flame"', '"cool flames"'], "llama fria": ['"cool flame"'],
    "llamas tibias": ['"warm flame"'], "llama tibia": ['"warm flame"'],
    "llama caliente": ['"hot flame"'], "llamas calientes": ['"hot flame"'],
    "llama de difusion": ['"diffusion flame"'], "llamas de difusion": ['"diffusion flame"'],
    "llama premezclada": ['"premixed flame"'], "llama invertida": ['"inverse flame"'],
    "limite de inflamabilidad": ['"flammability limit"'], "limites de inflamabilidad": ['"flammability limit"'],
    "propagacion de llama": ['"flame spread"'], "propagacion del fuego": ['"flame spread"', '"fire spread"'],
    "velocidad de propagacion": ['"spread rate"', '"flame spread"'],
    "extincion radiativa": ['"radiative extinction"'], "punto de humo": ['"smoke point"'],
    "tamano de particula": ['"particle size"'], "tamano de las particulas": ['"particle size"'],
    "indice de oxigeno": ['"oxygen index"'], "oxigeno minimo": ['"limiting oxygen"', '"minimum oxygen"'],
    "flujo de aire": ['"air flow"', '"flow velocity"'], "velocidad del flujo": ['"flow velocity"'],
    "concentracion de oxigeno": ['"oxygen concentration"'], "fraccion molar": ['"mole fraction"'],
    "presion parcial": ['"partial pressure"'], "gravedad parcial": ['"partial gravity"'],
    "baja gravedad": ['"low gravity"', "microgravity"], "gravedad normal": ['"normal gravity"'],
    "estacion espacial": ['"space station"', "iss"], "nave espacial": ["spacecraft"],
    "dioxido de carbono": ['"carbon dioxide"', "co2"], "agua nebulizada": ['"water mist"'],
    "agente extintor": ["suppressant", "extinguishant"], "agentes extintores": ["suppressant"],
    "monoxido de carbono": ['"carbon monoxide"'], "gases de combustion": ['"combustion products"'],
    # palabras sueltas
    "microgravedad": ["microgravity"], "ingravidez": ["microgravity", "weightlessness"],
    "llama": ["flame"], "llamas": ["flame"], "fuego": ["fire"], "incendio": ["fire"], "incendios": ["fire"],
    "combustion": ["combustion"], "combustible": ["fuel"], "combustibles": ["fuel"],
    "gota": ["droplet"], "gotas": ["droplet"], "hollin": ["soot"], "humo": ["smoke"],
    "extincion": ["extinction"], "apagado": ["extinction"], "ignicion": ["ignition"], "encendido": ["ignition"],
    "inflamabilidad": ["flammability"], "inflamable": ["flammable"], "propagacion": ["spread"],
    "oxigeno": ["oxygen"], "nitrogeno": ["nitrogen"], "helio": ["helium"], "dioxido": ["dioxide"],
    "presion": ["pressure"], "temperatura": ["temperature"], "radiacion": ["radiation"],
    "ventilacion": ["ventilation", "flow"], "convection": ["convection"], "conveccion": ["convection"],
    "difusion": ["diffusion"], "particulas": ["particle"], "particula": ["particle"],
    "deteccion": ["detection"], "detector": ["detector"], "detectores": ["detector"],
    "supresion": ["suppression"], "extintor": ["extinguisher"], "agente": ["agent"],
    "prevencion": ["prevention"], "riesgo": ["hazard", "risk"], "seguridad": ["safety"],
    "material": ["material"], "materiales": ["material"], "solido": ["solid"], "solidos": ["solid"],
    "liquido": ["liquid"], "liquidos": ["liquid"], "gaseoso": ["gaseous"], "gaseosos": ["gaseous"], "polimero": ["polymer"], "polimeros": ["polymer"],
    "tela": ["fabric"], "telas": ["fabric"], "algodon": ["cotton"], "cable": ["wire"], "cables": ["wire"],
    "plastico": ["plastic"], "plasticos": ["plastic"], "acrilico": ["acrylic", "pmma"],
    "heptano": ["heptane"], "decano": ["decane"], "metanol": ["methanol"], "etanol": ["ethanol"],
    "metano": ["methane"], "etileno": ["ethylene"], "propano": ["propane"],
    "luna": ["lunar", "moon"], "lunar": ["lunar"], "marte": ["mars"], "astronautas": ["crew"],
    "espesor": ["thickness"], "diametro": ["diameter"], "velocidad": ["velocity", "rate"],
}

# Palabras de la pregunta que no aportan a la búsqueda por palabras.
VACIAS = set("""que qué cual cuál cuales cuáles como cómo por para porque son es esta este estos estas del
las los una uno unos unas con sin sobre entre cuando donde dónde hay muy mas más menos puede pueden
the and for are what how why which with from does this that these those into about there their
psi nasa iss""".split())

ES = set("que qué de la el los las en y con para por un una es son cómo como cuál cuáles hay del al se".split())
EN = set("the of and in with how what does is are which why to for on by a an".split())


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def terminos_clave(pregunta: str) -> str:
    """Convierte la pregunta en una consulta para websearch_to_tsquery: términos unidos con OR."""
    texto = sin_acentos(pregunta)
    terminos: list[str] = []
    for frase in sorted(GLOSARIO, key=len, reverse=True):
        if re.search(rf"\b{re.escape(frase)}\b", texto):
            terminos += GLOSARIO[frase]
            texto = re.sub(rf"\b{re.escape(frase)}\b", " ", texto)
    # Lo que queda: siglas escritas en mayúsculas (FLEX, BASS-II, CO2, Saffire-II...) y, si la
    # pregunta está en inglés, también sus palabras normales.
    palabras = re.findall(r"[\wáéíóúñü]+", pregunta.lower())
    en_ingles = sum(p in EN for p in palabras) > sum(p in ES for p in palabras)
    siglas = {sin_acentos(x) for x in re.findall(r"\b[A-Z][A-Za-z\-]*[A-Z0-9][A-Za-z0-9\-]*\b", pregunta)}
    for palabra in re.findall(r"[a-z0-9][a-z0-9\-]{2,}", texto):
        if palabra not in VACIAS and (en_ingles or palabra in siglas):
            terminos.append(palabra)
    unicos = list(dict.fromkeys(t for t in terminos if re.fullmatch(r'"?[a-z0-9 \-]+"?', t)))
    return " OR ".join(unicos[:25])
