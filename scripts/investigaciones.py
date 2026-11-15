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

# Clasificación del equipo para el dashboard (según el texto del reto, no es un dato de PSI).
#   pilar:            prevencion | deteccion | supresion | contexto
#   tipo_combustible: solido | gota | gas | humo | polvo
#   familia_equipo:   agrupa experimentos que comparten equipo (lo pide el reto)
CATALOGO = {
    "PSI-26":  ("prevencion", "solido", "MSG - ducto de flujo SPICE", "Quema de telas y plásticos con flujo de aire; también prueba apagar con nitrógeno."),
    "PSI-25":  ("prevencion", "solido", "MSG - ducto de flujo SPICE", "Límites de inflamabilidad de PMMA y telas con distinto oxígeno y flujo de aire."),
    "PSI-98":  ("prevencion", "solido", "Cygnus - Saffire", "Incendio a gran escala de una tela de 94 x 40 cm en una nave de carga."),
    "PSI-99":  ("prevencion", "solido", "Cygnus - Saffire", "Nueve materiales en microgravedad comparados con la prueba estándar en la Tierra."),
    "PSI-100": ("prevencion", "solido", "Cygnus - Saffire", "Incendio a gran escala con mayor flujo de aire (30 cm/s)."),
    "PSI-102": ("deteccion", "humo", "MSG - SAME", "Tamaño de las partículas de humo de materiales sobrecalentados."),
    "PSI-101": ("deteccion", "humo", "MSG - SAME", "Segundo vuelo de SAME: más materiales, temperaturas y envejecimiento del humo."),
    "PSI-47":  ("deteccion", "polvo", "MSG - SAME", "Mide polvo en la ISS con el instrumento de humo de SAME (falsas alarmas)."),
    "PSI-69":  ("supresion", "gota", "CIR - MDCA (gotas)", "Extinción de gotas de combustible con CO2 y helio; descubrió las llamas frías."),
    "PSI-68":  ("supresion", "gota", "CIR - MDCA (gotas)", "Continuación de FLEX con más combustibles y condiciones."),
    "PSI-39":  ("supresion", "gota", "CIR - MDCA (gotas)", "Llamas frías: la gota sigue reaccionando después de apagarse la llama visible."),
    "PSI-20":  ("prevencion", "gas", "CIR - ACME (flamas de gas)", "Emula con gas cómo se queman materiales sólidos en aire quieto."),
    "PSI-21":  ("contexto", "gas", "CIR - ACME (flamas de gas)", "Estructura de flamas de gas con flujo paralelo de aire."),
    "PSI-22":  ("contexto", "gas", "CIR - ACME (flamas de gas)", "Efecto de campos eléctricos en flamas; imita la gravedad parcial."),
    "PSI-23":  ("contexto", "gas", "CIR - ACME (flamas de gas)", "Flamas esféricas de gas: estructura y extinción."),
    "PSI-10":  ("contexto", "gas", "CIR - ACME (flamas de gas)", "Límites de formación de hollín en flamas esféricas."),
    "PSI-159": ("contexto", "gas", "CIR - ACME (flamas de gas)", "Llamas frías con gases y oxígeno muy alto (hasta 85 %)."),
    "PSI-106": ("contexto", "gas", "MSG - ducto de flujo SPICE", "Estructura y desprendimiento de flamas de gas."),
    "PSI-107": ("contexto", "gas", "MSG - ducto de flujo SPICE", "Punto de humo: cuándo una flama de gas empieza a soltar hollín."),
    "PSI-117": ("supresion", "gota", "Estudio en tierra (datos de FLEX)", "Simulación por computadora de llamas frías con datos de FLEX."),
    "PSI-142": ("supresion", "gota", "Estudio en tierra (datos de FLEX)", "Simulaciones y pruebas en tierra de extinción de llamas frías."),
    "PSI-62":  ("prevencion", "solido", "Estudio en tierra (datos de BASS)", "Modelado de la propagación de flama comparado con BASS."),
    "PSI-60":  ("contexto", "gas", "Estudio en tierra (datos de SPICE)", "Análisis de hollín con los datos de SPICE."),
    "PSI-115": ("deteccion", "humo", "Estudio en tierra (datos de SAME)", "Simulación del crecimiento del humo con datos de SAME."),
}
