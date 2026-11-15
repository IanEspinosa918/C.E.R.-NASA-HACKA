"""Documentos GENERALES: guías, hojas informativas y presentaciones de programa.

PSI guarda algunos documentos generales dentro de la carpeta de un experimento. Por ejemplo,
la "ISS Researchers Guide - Combustion In Reduced Gravity" está en la carpeta de ACME BRE
(PSI-20), pero no es un resultado de ese experimento. Si se cita como "ACME BRE", quien lee
cree que el dato viene de ese experimento.

Aquí se listan esos documentos con una etiqueta correcta. buscar.preparar() la guarda en la
columna fragmentos.fuente_general (se aplica sola, no hay que recargar nada). Agrega reglas
aquí si encuentras otro documento general mal atribuido.
"""

from __future__ import annotations

# (expresión regular sobre titulo_documento o archivo, etiqueta que se mostrará)
REGLAS: list[tuple[str, str]] = [
    (r"Researchers.?Guide", "Guía general de la NASA: combustión en gravedad reducida (ISS)"),
    (r"FLEX.?A Decisive Step Forward", "Panorama general del programa de combustión de la NASA"),
    (r"CIR.?Paper", "Panorama general del Combustion Integrated Rack (CIR) de la ISS"),
    (r"Unlocking.?Mysteries", "Divulgación general de la NASA (programa ACME)"),
    (r"ACME.?(fact.?sheet|info.?sheet|pictorial|CDR|ASGSR|CSSCI|on.the.ISS)|PS[-_ ]?0\d{4}.?ACME",
     "Documento general del programa ACME (varios experimentos)"),
]


def sql_actualizar(tabla: str = "fragmentos") -> list[tuple[str, list]]:
    """Sentencias para crear la columna y etiquetar los documentos generales."""
    sentencias = [(f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS fuente_general text", [])]
    for patron, etiqueta in REGLAS:
        sentencias.append((
            f"UPDATE {tabla} SET fuente_general = %s "
            "WHERE fuente_general IS DISTINCT FROM %s AND (titulo_documento ~* %s OR archivo ~* %s)",
            [etiqueta, etiqueta, patron, patron]))
    return sentencias


def nombre_fuente(f: dict) -> str:
    """Nombre para mostrar: la etiqueta general si la tiene; si no, el experimento."""
    return f.get("fuente_general") or f["experimento"]
