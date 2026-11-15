"""Prueba la búsqueda del RAG: dada una pregunta, muestra los fragmentos más relevantes.

Búsqueda híbrida: por significado (vectores) + por palabras clave (texto completo de Postgres,
con glosario español->inglés), combinadas con Reciprocal Rank Fusion. Luego se eligen
fragmentos variados: sin casi-duplicados, máximo 2 por documento y 4 por experimento.

Esto es la mitad "buscar" del chat: el backend hará lo mismo y luego le pasará estos
fragmentos al modelo de IA para que redacte la respuesta con sus citas.
La función buscar() se puede importar desde el backend.

Uso:
  python scripts/buscar.py "¿qué son las llamas frías?"
  python scripts/buscar.py "how does CO2 extinguish a droplet flame" -k 8
  python scripts/buscar.py "tamaño de las partículas de humo" --experimento PSI-101
  python scripts/buscar.py "límite de inflamabilidad" --pilar prevencion
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bd  # noqa: E402
from embeddings import Vectorizador, a_pgvector, nombre_configurado  # noqa: E402
from fuentes_generales import nombre_fuente  # noqa: E402
from glosario import terminos_clave  # noqa: E402

CAMPOS = ["experimento", "experimento_id", "doi", "tipo_documento", "titulo_documento",
          "archivo", "pagina", "orden", "texto", "pilar", "fuente_general"]
CANDIDATOS = 40        # cuántos resultados pide cada búsqueda antes de combinar
RRF_K = 60             # constante estándar de Reciprocal Rank Fusion
POR_DOCUMENTO = 2      # máximo de fragmentos de un mismo archivo
POR_EXPERIMENTO = 4    # máximo de fragmentos de un mismo experimento
POR_GENERAL = 3        # máximo de fragmentos de documentos generales (guías, hojas informativas)
CASI_IGUAL = 0.8       # parecido de palabras (Jaccard) a partir del cual dos fragmentos son "el mismo"
TSV = "to_tsvector('english', texto)"  # debe coincidir con el índice fragmentos_texto_idx


def _filtros(vectorizador, experimento_id: str, pilar: str) -> tuple[list[str], list]:
    filtros, parametros = ["modelo_embedding = %s"], [vectorizador.nombre]
    if experimento_id:  # incluye documentos compartidos con ese experimento
        filtros.append("(experimento_id = %s OR %s = ANY(tambien_en))")
        parametros += [experimento_id, experimento_id]
    if pilar:
        filtros.append("pilar = %s")
        parametros.append(pilar)
    return filtros, parametros


def _por_vectores(cursor, vector: str, filtros, parametros, limite: int, tabla: str = "fragmentos") -> list[dict]:
    cursor.execute(
        f"SELECT {', '.join(CAMPOS)}, 1 - (embedding <=> %s::vector) AS similitud "
        f"FROM {tabla} WHERE {' AND '.join(filtros)} ORDER BY embedding <=> %s::vector LIMIT %s",
        [vector] + parametros + [vector, limite])
    return [dict(zip(CAMPOS + ["similitud"], fila)) for fila in cursor.fetchall()]


def _por_palabras(cursor, consulta: str, vector: str, filtros, parametros, limite: int,
                  tabla: str = "fragmentos") -> list[dict]:
    if not consulta:
        return []
    cursor.execute(
        f"SELECT {', '.join(CAMPOS)}, 1 - (embedding <=> %s::vector) AS similitud "
        f"FROM {tabla}, websearch_to_tsquery('english', %s) AS q "
        f"WHERE {TSV} @@ q AND {' AND '.join(filtros)} "
        f"ORDER BY ts_rank_cd({TSV}, q) DESC LIMIT %s",
        [vector, consulta] + parametros + [limite])
    return [dict(zip(CAMPOS + ["similitud"], fila)) for fila in cursor.fetchall()]


def _palabras(texto: str) -> set[str]:
    import re
    return set(re.findall(r"[a-z0-9]{3,}", texto.lower()))


def diversificar(candidatos: list[dict], k: int, limitar: bool = True) -> list[dict]:
    """Elige k fragmentos en orden de relevancia, sin casi-duplicados y (si limitar) con
    máximo POR_DOCUMENTO por archivo y POR_EXPERIMENTO por experimento. Si con los límites
    no se juntan k, se completa con los que se saltaron (en orden de relevancia)."""
    elegidos, saltados, vistos = [], [], []
    por_doc: dict[str, int] = {}
    por_exp: dict[str, int] = {}
    for c in candidatos:
        palabras = _palabras(c["texto"])
        if any(len(palabras & v) / max(1, len(palabras | v)) >= CASI_IGUAL for v in vistos):
            continue  # casi idéntico a uno ya elegido (p. ej. la misma hoja en dos experimentos)
        grupo = "general" if c.get("fuente_general") else c["experimento_id"]
        tope = POR_GENERAL if grupo == "general" else POR_EXPERIMENTO
        if limitar and (por_doc.get(c["archivo"], 0) >= POR_DOCUMENTO or por_exp.get(grupo, 0) >= tope):
            saltados.append((c, palabras))
            continue
        elegidos.append(c)
        vistos.append(palabras)
        por_doc[c["archivo"]] = por_doc.get(c["archivo"], 0) + 1
        por_exp[grupo] = por_exp.get(grupo, 0) + 1
        if len(elegidos) == k:
            return elegidos
    for c, palabras in saltados:
        if len(elegidos) == k:
            break
        if not any(len(palabras & v) / max(1, len(palabras | v)) >= CASI_IGUAL for v in vistos):
            elegidos.append(c)
            vistos.append(palabras)
    return elegidos


def buscar(conexion, vectorizador: Vectorizador, pregunta: str, k: int = 5,
           experimento_id: str = "", pilar: str = "", hibrida: bool = True,
           diversa: bool = True) -> list[dict]:
    """Regresa k fragmentos relevantes a la pregunta, con metadatos y similitud (0 a 1).

    - hibrida: combina la búsqueda por significado (vectores) con la de palabras clave
      (texto completo de Postgres, con el glosario español->inglés), usando Reciprocal Rank
      Fusion: un fragmento que sale arriba en las dos sube más.
    - diversa: evita casi-duplicados y limita fragmentos por documento y por experimento
      (los límites no se aplican si se filtra por un experimento)."""
    vector = a_pgvector(vectorizador.pregunta(pregunta))
    filtros, parametros = _filtros(vectorizador, experimento_id, pilar)
    cursor = conexion.cursor()
    limite = max(CANDIDATOS, k * 4) if (hibrida or diversa) else k
    tabla = vectorizador.tabla
    por_vector = _por_vectores(cursor, vector, filtros, parametros, limite, tabla)

    por_texto = []
    if hibrida:
        try:
            por_texto = _por_palabras(cursor, terminos_clave(pregunta), vector, filtros, parametros, limite, tabla)
        except Exception:  # sin búsqueda de texto disponible: seguimos sólo con vectores
            conexion.rollback()

    combinados: dict[tuple, dict] = {}
    for lista, via in ((por_vector, "significado"), (por_texto, "palabras")):
        for posicion, f in enumerate(lista, 1):
            clave = (f["archivo"], f["orden"])
            if clave not in combinados:
                combinados[clave] = {**f, "puntaje": 0.0, "via": via}
            elif combinados[clave]["via"] != via:
                combinados[clave]["via"] = "ambas"
            combinados[clave]["puntaje"] += 1 / (RRF_K + posicion)
    candidatos = sorted(combinados.values(), key=lambda f: f["puntaje"], reverse=True)
    if not diversa:
        return candidatos[:k]
    return diversificar(candidatos, k, limitar=not experimento_id)


PILARES = {  # consultas en inglés: los documentos están en inglés
    "prevencion": "flammability limit and flame spread of solid materials, oxygen concentration, "
                  "pressure and air flow velocity in microgravity",
    "deteccion": "smoke particle size, fire detection and smoke detectors in microgravity, "
                 "combustion products and aerosol",
    "supresion": "flame extinction and fire suppression in microgravity, extinguishing agents, "
                 "carbon dioxide, nitrogen and helium diluents",
}


def buscar_por_pilares(conexion, vectorizador: Vectorizador, pregunta: str, k: int = 9,
                       por_pilar: int = 3) -> list[dict]:
    """Para el dictamen de un escenario: una búsqueda con la pregunta y una por cada pilar
    (prevención, detección, supresión), filtrando por los experimentos de ese pilar. Se
    intercalan los resultados para que la respuesta tenga material de los tres pilares."""
    listas = [buscar(conexion, vectorizador, pregunta, por_pilar)]
    for pilar, consulta in PILARES.items():
        listas.append(buscar(conexion, vectorizador, consulta, por_pilar, pilar=pilar))
    intercalados, vistos = [], set()
    for posicion in range(max(len(lista) for lista in listas)):
        for lista in listas:
            if posicion < len(lista) and (lista[posicion]["archivo"], lista[posicion]["orden"]) not in vistos:
                vistos.add((lista[posicion]["archivo"], lista[posicion]["orden"]))
                intercalados.append(lista[posicion])
    return diversificar(intercalados, k)


def preparar_texto_completo(conexion, tabla: str = "fragmentos") -> bool:
    """Crea (una sola vez) el índice para la búsqueda por palabras y etiqueta los documentos
    generales (ver fuentes_generales.py). Regresa si la búsqueda por palabras quedó disponible."""
    from fuentes_generales import sql_actualizar
    # Si otro servidor (otra revisión de Cloud Run, o el backend de alguien del equipo) tiene la tabla en uso,
    # no esperar: con lock_timeout cada paso se rinde a los 5 s y el servidor arranca igual.
    _sql_seguro(conexion, "SET lock_timeout = '5s'")
    sentencias = sql_actualizar(tabla)
    if _tiene_columna(conexion, tabla, "fuente_general"):
        # ALTER TABLE pide un candado exclusivo AUNQUE la columna ya exista: se salta si ya está
        sentencias = [s for s in sentencias if not s[0].lstrip().upper().startswith("ALTER TABLE")]
    try:  # columna y etiquetas de documentos generales (rápido; sólo cambia lo que falte)
        cursor = conexion.cursor()
        for sql, parametros in sentencias:
            cursor.execute(sql, parametros)
        conexion.commit()
    except Exception:
        conexion.rollback()
    try:
        cursor = conexion.cursor()
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {tabla}_texto_idx ON {tabla} USING gin ({TSV})")
        conexion.commit()
        return True
    except Exception:
        conexion.rollback()
        return _sql_seguro(conexion, f"SELECT to_regclass('public.{tabla}_texto_idx') IS NOT NULL", leer=True) is True


def _sql_seguro(conexion, sql: str, leer: bool = False):
    """Ejecuta una sentencia sin dejar la transacción abierta ni lanzar errores."""
    try:
        cursor = conexion.cursor()
        cursor.execute(sql)
        valor = cursor.fetchone()[0] if leer else None
        conexion.commit()
        return valor
    except Exception:
        try:
            conexion.rollback()
        except Exception:
            pass
        return None


def _tiene_columna(conexion, tabla: str, columna: str) -> bool:
    return _sql_seguro(conexion, "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = "
                                 f"'public' AND table_name = '{tabla}' AND column_name = '{columna}')", leer=True) is True


def con_vecinos(conexion, fragmentos: list[dict], alcance: int = 1, tabla: str = "fragmentos") -> list[dict]:
    """Agrega a cada fragmento el texto de los vecinos (orden ± alcance) del mismo archivo,
    para que el modelo de IA tenga el párrafo completo y no sólo un pedazo de 500 caracteres.
    Si dos resultados son vecinos entre sí, se quedan como uno solo (sin repetir texto)."""
    cursor = conexion.cursor()
    ampliados, cubiertos = [], set()
    for f in fragmentos:
        if (f["archivo"], f["orden"]) in cubiertos:
            continue  # ya viene dentro del texto ampliado de un resultado anterior
        cursor.execute(f"SELECT orden, texto FROM {tabla} WHERE archivo = %s AND orden BETWEEN %s AND %s "
                       "ORDER BY orden", [f["archivo"], f["orden"] - alcance, f["orden"] + alcance])
        filas = [fila for fila in cursor.fetchall() if (f["archivo"], fila[0]) not in cubiertos]
        cubiertos.update((f["archivo"], fila[0]) for fila in filas)
        ampliados.append({**f, "texto": " ".join(t for _, t in filas) or f["texto"]})
    return ampliados


def preparar(conexion, modelo: str | None = None) -> Vectorizador:
    """Crea el Vectorizador y revisa que su tabla exista y tenga fragmentos de ese modelo.
    Cada modelo de embeddings tiene su propia tabla (ver embeddings.tabla_fragmentos)."""
    from embeddings import tabla_fragmentos
    nombre = nombre_configurado(modelo)
    tabla = tabla_fragmentos(nombre)
    # Revisión previa (sin cargar el modelo) para no descargar 220 MB en vano.
    if not bd.uno(conexion, f"SELECT to_regclass('public.{tabla}') IS NOT NULL"):
        raise SystemExit(f"No existe la tabla {tabla} para el modelo '{nombre}'. Cárgala con:\n"
                         f"  python scripts/cargar_fragmentos.py --modelo {nombre.split('@')[0]}")
    cursor = conexion.cursor()
    cursor.execute(f"SELECT modelo_embedding, count(*) FROM {tabla} GROUP BY 1")
    cargados = dict(cursor.fetchall())
    if not cargados:
        raise SystemExit(f"La tabla {tabla} está vacía. Corre: python scripts/cargar_fragmentos.py")
    if nombre not in cargados and not any(c.split("@")[0] == nombre.split("@")[0] for c in cargados):
        raise SystemExit(f"La tabla {tabla} tiene fragmentos de {list(cargados)} y estás preguntando con "
                         f"'{nombre}'. Revisa MODELO_EMBEDDINGS en .env.")
    vectorizador = Vectorizador(nombre)
    preparar_texto_completo(conexion, tabla)
    if vectorizador.nombre not in cargados:
        raise SystemExit(f"La tabla {tabla} tiene fragmentos de {list(cargados)} y estás preguntando con "
                         f"'{vectorizador.nombre}'. Revisa MODELO_EMBEDDINGS y DIMENSIONES_EMBEDDINGS en .env.")
    return vectorizador


def main() -> int:
    p = argparse.ArgumentParser(description="Busca fragmentos parecidos a una pregunta.")
    p.add_argument("pregunta")
    p.add_argument("-k", type=int, default=5, help="cuántos fragmentos mostrar (default 5)")
    p.add_argument("--experimento", default="", help="sólo este experimento (ej. PSI-69)")
    p.add_argument("--pilar", default="", help="prevencion | deteccion | supresion | contexto")
    p.add_argument("--modelo", help="modelo de embeddings (debe ser el mismo con el que se cargó)")
    p.add_argument("--solo-vectores", action="store_true", help="sin búsqueda por palabras clave")
    p.add_argument("--sin-diversidad", action="store_true", help="sin límites por documento/experimento")
    p.add_argument("--por-pilar", action="store_true", help="una búsqueda por pilar (como el dictamen)")
    args = p.parse_args()

    conexion = bd.conectar()
    vectorizador = preparar(conexion, args.modelo)
    from gemini import ErrorIA
    try:
        if args.por_pilar:
            resultados = buscar_por_pilares(conexion, vectorizador, args.pregunta, args.k)
        else:
            resultados = buscar(conexion, vectorizador, args.pregunta, args.k, args.experimento, args.pilar,
                                hibrida=not args.solo_vectores, diversa=not args.sin_diversidad)
    except ErrorIA as e:
        raise SystemExit(f"Error al vectorizar la pregunta:\n{e}")
    if not resultados:
        print("Sin resultados.")
        return 0
    print(f'\nPregunta: "{args.pregunta}"')
    print(f"Palabras clave usadas: {terminos_clave(args.pregunta) or '(ninguna)'}\n")
    for i, r in enumerate(resultados, start=1):
        pagina = f", pág. {r['pagina']}" if r["pagina"] else ""
        print(f"{i}. [{r['similitud']:.2f} · {r.get('via', 'significado')} · {r.get('pilar') or '-'}] "
              f"{nombre_fuente(r)} ({r['experimento_id']}) · {r['tipo_documento']} · "
              f"{r['titulo_documento']}{pagina}")
        print(f"   DOI {r['doi']} · {r['archivo']}")
        print(f"   {r['texto']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
