"""Decide en qué idioma responde la IA: español ("es") o inglés ("en").

Orden:
  1. Si la pregunta lo pide de forma explícita ("respond in English", "contéstame en inglés",
     "in Spanish please"), se respeta.
  2. Si no, se cuentan palabras típicas de cada idioma en la pregunta (y acentos, ñ, ¿ ¡).
  3. Si empata (pregunta muy corta o sólo siglas, como "FLEX-2"), se usa el idioma de la página.
"""

from __future__ import annotations

import re

_PIDE_INGLES = re.compile(
    r"\b(in english|en ingl[eé]s|answer in english|respond in english|reply in english|"
    r"english please|in english please)\b", re.IGNORECASE)
_PIDE_ESPANOL = re.compile(
    r"\b(in spanish|en espa[ñn]ol|answer in spanish|respond in spanish|en castellano)\b", re.IGNORECASE)

_ES = set("""que qué de la el los las en y con para por un una es son cómo como cuál cuáles hay del al se
qué porque cuando donde dónde muy más menos pero también sobre entre sin esto esta este estos estas
llama llamas fuego incendio humo oxígeno gravedad experimento experimentos nave misión qué dime explica
puedes podrías cuánto cuánta cuántos sirve sirven""".split())
_EN = set("""the of and in with how what does is are which why to for on by an do did was were this that
these those can could would should about from into when where who fire flame flames smoke oxygen gravity
experiment experiments spacecraft mission tell explain please you your it its than then there""".split())


def detectar_idioma(pregunta: str, preferido: str = "es") -> str:
    """Regresa "en" o "es"."""
    preferido = preferido if preferido in ("es", "en") else "es"
    texto = pregunta or ""
    if _PIDE_INGLES.search(texto):
        return "en"
    if _PIDE_ESPANOL.search(texto):
        return "es"
    palabras = re.findall(r"[a-záéíóúüñ']+", texto.lower())
    es = sum(p in _ES for p in palabras) + 2 * len(re.findall(r"[¿¡ñáéíóú]", texto.lower()))
    en = sum(p in _EN for p in palabras)
    if en > es:
        return "en"
    if es > en:
        return "es"
    return preferido
