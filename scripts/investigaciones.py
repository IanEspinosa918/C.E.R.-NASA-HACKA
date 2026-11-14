"""Lista de experimentos de PSI que usa el proyecto.

La búsqueda "combustion" de PSI trae 26 resultados, pero PSI-181 (soldaduras) y
PSI-108 (fluidos) no son de fuego, y le falta DAFT (PSI-47). Esta lista ya está
corregida. Ver docs/fuentes.md.
"""

# Experimentos realizados en el espacio (vuelo)
VUELO = {
    "PSI-26": "BASS",
    "PSI-25": "BASS-II",
    "PSI-98": "SAFFIRE-I",
    "PSI-99": "SAFFIRE-II",
    "PSI-100": "SAFFIRE-III",
    "PSI-102": "SAME",
    "PSI-101": "SAME-R",
    "PSI-47": "DAFT",
    "PSI-69": "FLEX",
    "PSI-68": "FLEX-2",
    "PSI-39": "CFI",
    "PSI-20": "ACME-BRE",
    "PSI-21": "ACME-CLD",
    "PSI-22": "ACME-E-FIELD",
    "PSI-23": "ACME-s-Flame",
    "PSI-10": "ACME-Flame-Design",
    "PSI-159": "ACME-CFI-G",
    "PSI-106": "SLICE",
    "PSI-107": "SPICE",
}

# Estudios en tierra que analizan o modelan datos de vuelo (no son mediciones nuevas)
TIERRA = {
    "PSI-117": "Tierra-FLEX-CoolFlame-CFD",
    "PSI-142": "Tierra-FLEX-CoolFlame-Extincion",
    "PSI-62": "Tierra-BASS-Modelado",
    "PSI-60": "Tierra-SPICE-Hollin",
    "PSI-115": "Tierra-SAME-Humo",
}

TODAS = {**VUELO, **TIERRA}
