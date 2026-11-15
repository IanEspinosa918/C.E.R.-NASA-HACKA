"""Filtro de seguridad ANTES de mandar la pregunta a la IA.

Dos capas de protección:
  1. Este filtro (determinista): detecta frases claras de intención de hacer daño a otros,
     sabotaje, o de autolesión, y responde con un mensaje fijo SIN llamar a la IA.
  2. Las reglas de llm.py: la IA también se niega a esos temas aunque la pregunta pase el filtro.

La lista es corta a propósito: preguntas legítimas como "¿qué puede provocar un incendio en
una nave?" o "¿cómo se enciende una gota en FLEX?" son de PREVENCIÓN y no se bloquean.
Si una pregunta legítima se bloquea por error, ajusta los patrones aquí.
"""

from __future__ import annotations

import re
import unicodedata

AYUDA = (
    "Siento que estés pasando por algo así. Lo que sientes importa y no tienes que enfrentarlo solo.\n\n"
    "Si estás en peligro o crees que podrías hacerte daño, llama ahora a emergencias (911). "
    "En México también puedes llamar a la Línea de la Vida, 800 911 2000, gratis y a cualquier hora. "
    "Si estás en otro país, busca la línea de crisis local o acude al servicio de urgencias más cercano.\n\n"
    "También puede ayudar hablar con alguien de confianza: un familiar, un amigo o un profesor."
)

NEGATIVA = (
    "No puedo ayudar con eso. Este asistente está hecho para PREVENIR, detectar y apagar incendios en "
    "misiones espaciales, no para causar daño, sabotear equipos o desactivar sistemas de seguridad.\n\n"
    "Si te interesa, puedo explicarte qué dicen los experimentos de NASA PSI sobre cómo prevenir que "
    "un incendio empiece o cómo se detecta a tiempo."
)

HELP_EN = (
    "I'm really sorry you're going through this. What you feel matters, and you don't have to face it alone.\n\n"
    "If you are in danger or think you might hurt yourself, call your local emergency number now (911 in the US "
    "and Mexico). In the US you can also call or text 988 (Suicide & Crisis Lifeline); in Mexico, Línea de la "
    "Vida 800 911 2000. In other countries, look for your local crisis line or go to the nearest emergency room.\n\n"
    "Talking to someone you trust, like a friend, a family member or a teacher, can also help."
)

REFUSAL_EN = (
    "I can't help with that. This assistant is built to PREVENT, detect and put out fires on space missions, "
    "not to cause harm, sabotage equipment or disable safety systems.\n\n"
    "If you're interested, I can explain what the NASA PSI experiments say about preventing a fire from "
    "starting or detecting it early."
)

# Autolesión: frases en primera persona.
_AUTOLESION = [
    r"\bsuicid", r"\bquitarme la vida\b", r"\bmatarme\b", r"\bme quiero morir\b", r"\bquiero morir(me)?\b",
    r"\b(quiero|voy a|pienso|pensando en) (hacerme dano|lastimarme|quemarme|cortarme)\b",
    r"\bautolesion", r"\bme quiero (quemar|lastimar|cortar)\b",
    r"\bkill myself\b", r"\bhurt myself\b", r"\bself[- ]harm\b", r"\bsuicid",
    r"\bend my life\b", r"\bi (want|wanna) to die\b", r"\bi don.?t want to (live|be alive)\b",
    r"\b(want to|going to|thinking about|gonna) (burn|cut|harm) myself\b",
]

# Daño a otros, sabotaje, evadir sistemas de seguridad.
_DANO = [
    r"\bsin que (se den cuenta|nadie se de cuenta|me descubran|lo detecten)\b",
    r"\b(sabotear|sabotaje)\b", r"\bsabotage\b",
    r"\b(desactiv|bloque|engan|burl|evad|anul|deshabilit|inutiliz|sabote)\w*\b.{0,40}"
    r"\b(detector|detectores|sensor|sensores|alarma|alarmas|extintor|extintores|supresion|rociador)",
    r"\b(disable|bypass|fool|trick)\b.{0,40}\b(detector|sensor|alarm|suppression|extinguisher)",
    r"\b(provoc|inici|caus|empez|empiez|prend|hag|hac)\w*\b.{0,25}\b(incendio|fuego|explosion)\b.{0,40}"
    r"\b(a proposito|intencional|para (danar|lastimar|matar|destruir|vengarme)|contra)\b",
    r"\b(como|quiero|voy a|puedo|podria|ayudame a)\b.{0,15}"
    r"\b(quem|incendi|lastim|danar|her|mat|envenen|asfixi)\w*\b.{0,20}"
    r"\b(a (alguien|una persona|la tripulacion|los astronautas|mi|un|una)|al (astronauta|companero))",
    r"\b(hag|hac|fabric|arm|constru)\w* (una |un )?(bomba|explosivo|artefacto incendiario)\b",
    r"\b(coctel )?molotov\b", r"\bnapalm casero\b",
    r"\b(arson|incendiary device|make a bomb|explosive device)\b",
    r"\b(set fire to|burn down)\b.{0,15}\b(someone|somebody|a person|people|the crew|my|his|her|their|the (station|ship|"
    r"spacecraft|habitat|module|cabin|house|building|lab))\b",
    # Inglés: sin que se note, provocar un incendio a propósito, dañar a alguien
    r"\bwithout (anyone|them|the crew|mission control|anybody) (noticing|knowing|finding out)\b",
    r"\b(start|cause|light|set)\b.{0,25}\b(fire|explosion)\b.{0,40}"
    r"\b(on purpose|intentionally|deliberately|to (hurt|harm|kill|destroy|get back at))\b",
    r"\b(how (to|do i|can i|could i)|i want to|help me|i.m going to)\b.{0,15}"
    r"\b(burn|hurt|harm|kill|poison|suffocate|injure)\b.{0,20}"
    r"\b(someone|somebody|a person|people|the crew|the astronauts|an astronaut|my (crewmate|coworker|colleague))",
    r"\b(make|build|assemble)\b.{0,10}\b(a )?(bomb|explosive|incendiary)\b",
    r"\b(deactivat|turn off|switch off|tamper with|silence|cover)\w*\b.{0,30}"
    r"\b(smoke detector|fire alarm|detectors|alarms|sprinkler|suppression system)\b.{0,40}"
    r"\b(so (that )?(no one|nobody|they|the crew)|without|secretly|unnoticed)\b",
]


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def revisar_pregunta(pregunta: str, idioma: str = "es") -> tuple[str, str] | None:
    """Regresa (categoria, respuesta_fija) si la pregunta no debe ir a la IA; si no, None.
    Los patrones cubren español e inglés; `idioma` sólo elige el idioma de la respuesta fija."""
    texto = _normalizar(pregunta)
    if any(re.search(p, texto) for p in _AUTOLESION):
        return "autolesion", HELP_EN if idioma == "en" else AYUDA
    if any(re.search(p, texto) for p in _DANO):
        return "dano", REFUSAL_EN if idioma == "en" else NEGATIVA
    return None
