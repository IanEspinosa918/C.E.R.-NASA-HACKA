"""Prueba la búsqueda del RAG: dada una pregunta, muestra los fragmentos más parecidos.

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

CAMPOS = ["experimento", "experimento_id", "doi", "tipo_documento", "titulo_documento",
          "archivo", "pagina", "orden", "texto"]


def buscar(conexion, vectorizador: Vectorizador, pregunta: str, k: int = 5,
           experimento_id: str = "", pilar: str = "") -> list[dict]:
    """Regresa los k fragmentos más parecidos a la pregunta, con sus metadatos y similitud (0 a 1)."""
    vector = a_pgvector(vectorizador.pregunta(pregunta))
    filtros, parametros = ["modelo_embedding = %s"], [vector, vectorizador.nombre]
    if experimento_id:  # incluye documentos compartidos con ese experimento
        filtros.append("(experimento_id = %s OR %s = ANY(tambien_en))")
        parametros += [experimento_id, experimento_id]
    if pilar:
        filtros.append("pilar = %s")
        parametros.append(pilar)
    sql = (f"SELECT {', '.join(CAMPOS)}, 1 - (embedding <=> %s::vector) AS similitud "
           f"FROM fragmentos WHERE {' AND '.join(filtros)} "
           "ORDER BY embedding <=> %s::vector LIMIT %s")
    cursor = conexion.cursor()
    cursor.execute(sql, parametros + [vector, k])
    return [dict(zip(CAMPOS + ["similitud"], fila)) for fila in cursor.fetchall()]


def con_vecinos(conexion, fragmentos: list[dict], alcance: int = 1) -> list[dict]:
    """Agrega a cada fragmento el texto de los vecinos (orden ± alcance) del mismo archivo,
    para que el modelo de IA tenga el párrafo completo y no sólo un pedazo de 500 caracteres.
    Si dos resultados son vecinos entre sí, se quedan como uno solo (sin repetir texto)."""
    cursor = conexion.cursor()
    ampliados, cubiertos = [], set()
    for f in fragmentos:
        if (f["archivo"], f["orden"]) in cubiertos:
            continue  # ya viene dentro del texto ampliado de un resultado anterior
        cursor.execute("SELECT orden, texto FROM fragmentos WHERE archivo = %s AND orden BETWEEN %s AND %s "
                       "ORDER BY orden", [f["archivo"], f["orden"] - alcance, f["orden"] + alcance])
        filas = [fila for fila in cursor.fetchall() if (f["archivo"], fila[0]) not in cubiertos]
        cubiertos.update((f["archivo"], fila[0]) for fila in filas)
        ampliados.append({**f, "texto": " ".join(t for _, t in filas) or f["texto"]})
    return ampliados


def preparar(conexion, modelo: str | None = None) -> Vectorizador:
    """Crea el Vectorizador y revisa que coincida con el modelo de los fragmentos cargados."""
    if not bd.uno(conexion, "SELECT to_regclass('public.fragmentos') IS NOT NULL"):
        raise SystemExit("La base no tiene fragmentos. Corre: python scripts/cargar_fragmentos.py")
    cursor = conexion.cursor()
    cursor.execute("SELECT DISTINCT modelo_embedding FROM fragmentos")
    cargados = [f[0] for f in cursor.fetchall()]
    nombre = nombre_configurado(modelo)
    # Revisión previa (sin cargar el modelo) para no descargar 220 MB en vano.
    if cargados and nombre not in cargados and not any(c.split("@")[0] == nombre.split("@")[0] for c in cargados):
        raise SystemExit(f"Los fragmentos se cargaron con {cargados} y estás preguntando con '{nombre}'.\n"
                         "Deben ser el mismo modelo (revisa MODELO_EMBEDDINGS en .env), o vuelve a cargar con\n"
                         "  python scripts/cargar_fragmentos.py --recrear")
    vectorizador = Vectorizador(nombre)
    if cargados and vectorizador.nombre not in cargados:
        raise SystemExit(f"Los fragmentos se cargaron con {cargados} y estás preguntando con "
                         f"'{vectorizador.nombre}'. Revisa MODELO_EMBEDDINGS y DIMENSIONES_EMBEDDINGS en .env.")
    return vectorizador


def main() -> int:
    p = argparse.ArgumentParser(description="Busca fragmentos parecidos a una pregunta.")
    p.add_argument("pregunta")
    p.add_argument("-k", type=int, default=5, help="cuántos fragmentos mostrar (default 5)")
    p.add_argument("--experimento", default="", help="sólo este experimento (ej. PSI-69)")
    p.add_argument("--pilar", default="", help="prevencion | deteccion | supresion | contexto")
    p.add_argument("--modelo", help="modelo de embeddings (debe ser el mismo con el que se cargó)")
    args = p.parse_args()

    conexion = bd.conectar()
    vectorizador = preparar(conexion, args.modelo)
    from gemini import ErrorGemini
    try:
        resultados = buscar(conexion, vectorizador, args.pregunta, args.k, args.experimento, args.pilar)
    except ErrorGemini as e:
        raise SystemExit(f"Error al vectorizar la pregunta con Gemini:\n{e}")
    if not resultados:
        print("Sin resultados.")
        return 0
    print(f'\nPregunta: "{args.pregunta}"\n')
    for i, r in enumerate(resultados, start=1):
        pagina = f", pág. {r['pagina']}" if r["pagina"] else ""
        print(f"{i}. [{r['similitud']:.2f}] {r['experimento']} ({r['experimento_id']}) · {r['tipo_documento']} · "
              f"{r['titulo_documento']}{pagina}")
        print(f"   DOI {r['doi']} · {r['archivo']}")
        print(f"   {r['texto']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
