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
from embeddings import MODELO_POR_DEFECTO, Vectorizador, a_pgvector  # noqa: E402

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


def main() -> int:
    p = argparse.ArgumentParser(description="Busca fragmentos parecidos a una pregunta.")
    p.add_argument("pregunta")
    p.add_argument("-k", type=int, default=5, help="cuántos fragmentos mostrar (default 5)")
    p.add_argument("--experimento", default="", help="sólo este experimento (ej. PSI-69)")
    p.add_argument("--pilar", default="", help="prevencion | deteccion | supresion | contexto")
    p.add_argument("--modelo", help="modelo de embeddings (debe ser el mismo con el que se cargó)")
    args = p.parse_args()

    conexion = bd.conectar()
    if not bd.uno(conexion, "SELECT to_regclass('public.fragmentos') IS NOT NULL"):
        raise SystemExit("La base no tiene fragmentos. Corre: python scripts/cargar_fragmentos.py")
    cursor = conexion.cursor()
    cursor.execute("SELECT DISTINCT modelo_embedding FROM fragmentos")
    cargados = [f[0] for f in cursor.fetchall()]
    modelo = args.modelo or bd.leer_env().get("MODELO_EMBEDDINGS") or (cargados[0] if cargados else MODELO_POR_DEFECTO)
    if cargados and modelo not in cargados:
        raise SystemExit(f"Los fragmentos se cargaron con {cargados} y estás preguntando con '{modelo}'.\n"
                         "Deben ser el mismo modelo (revisa MODELO_EMBEDDINGS en .env).")

    resultados = buscar(conexion, Vectorizador(modelo), args.pregunta, args.k, args.experimento, args.pilar)
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
