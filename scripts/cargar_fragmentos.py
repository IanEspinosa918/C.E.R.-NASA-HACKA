"""Calcula los vectores (embeddings) de los fragmentos y los sube a Postgres (pgvector).

Entrada:  data/processed/fragmentos.jsonl     (de scripts/preparar_textos.py)
Destino:  tabla `fragmentos` de la base de DATABASE_URL (archivo .env)

Antes hay que haber corrido scripts/cargar_bd.py (crea la tabla `experimentos`).

Con el modelo local (por defecto) todo corre en tu computadora (gratis, sin claves). La
primera vez se descarga (~220 MB). Con unos 20 mil fragmentos tarda de 10 a 30 minutos.

Uso:
  python scripts/cargar_fragmentos.py               # borra los fragmentos y los carga todos
  python scripts/cargar_fragmentos.py --continuar   # retoma una carga que se interrumpió
  python scripts/cargar_fragmentos.py --recrear     # borra la tabla (necesario si cambias de modelo)
  python scripts/cargar_fragmentos.py --limite 200  # prueba rápida con pocos fragmentos

Con Gemini (MODELO_EMBEDDINGS=gemini-embedding-001 en .env) los vectores se calculan en
la API de Google: no usa tu computadora, pero tiene límites por minuto y por día.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bd  # noqa: E402
import comun_limpieza as cl  # noqa: E402
from embeddings import MODELO_DE_PRUEBA, MODELO_POR_DEFECTO, Vectorizador, a_pgvector, es_gemini, nombre_configurado  # noqa: E402

ENTRADA = cl.DIR_PROCESSED / "fragmentos.jsonl"
COLUMNAS = ["experimento_id", "experimento", "pilar", "doi", "tipo_documento", "titulo_documento",
            "archivo", "pagina", "orden", "texto", "tambien_en", "modelo_embedding", "embedding"]
CONVERSIONES = {"pagina": "::integer", "orden": "::integer", "tambien_en": "::text[]", "embedding": "::vector"}


def main() -> int:
    p = argparse.ArgumentParser(description="Sube los fragmentos con sus vectores a Postgres.")
    p.add_argument("--modelo", help=f"modelo de embeddings (default: MODELO_EMBEDDINGS de .env o {MODELO_POR_DEFECTO})")
    p.add_argument("--continuar", action="store_true", help="no borra; sólo agrega los fragmentos que falten")
    p.add_argument("--recrear", action="store_true", help="borra y vuelve a crear la tabla fragmentos")
    p.add_argument("--limite", type=int, default=0, help="cargar sólo los primeros N fragmentos (para probar)")
    p.add_argument("--lote", type=int, default=0, help="fragmentos por lote (default 128; 100 con Gemini)")
    args = p.parse_args()

    if not ENTRADA.exists():
        raise SystemExit("No existe data/processed/fragmentos.jsonl. Corre primero: python scripts/preparar_textos.py")
    with open(ENTRADA, encoding="utf-8") as f:
        fragmentos = [json.loads(linea) for linea in f if linea.strip()]
    if args.limite:
        fragmentos = fragmentos[: args.limite]

    conexion = bd.conectar()
    if not bd.uno(conexion, "SELECT to_regclass('public.experimentos') IS NOT NULL"):
        raise SystemExit("La base no tiene la tabla experimentos. Corre primero: python scripts/cargar_bd.py")

    vectorizador = Vectorizador(nombre_configurado(args.modelo))
    nombre_modelo = vectorizador.nombre
    if nombre_modelo == MODELO_DE_PRUEBA:
        print("AVISO: modelo 'prueba' = vectores falsos. Sirve para probar la carga, NO para el chat.")
    print(f"Modelo: {nombre_modelo} ({vectorizador.dimension} dimensiones)")
    if es_gemini(nombre_modelo):
        print("Usando la API de Gemini: si se alcanza el límite por minuto el script espera solo; "
              "si se acaba la cuota del día, se detiene y se retoma con --continuar.")

    if not args.lote:
        args.lote = 100 if es_gemini(nombre_modelo) else 128

    cursor = conexion.cursor()
    if args.recrear:
        cursor.execute("DROP TABLE IF EXISTS fragmentos")
    bd.aplicar(conexion, "fragmentos", {"vector(384)": f"vector({vectorizador.dimension})"})
    conexion.commit()

    dimension_tabla = bd.uno(conexion, "SELECT atttypmod FROM pg_attribute WHERE attrelid = 'fragmentos'::regclass "
                                       "AND attname = 'embedding'")
    if dimension_tabla != vectorizador.dimension:
        raise SystemExit(f"La tabla fragmentos guarda vectores de {dimension_tabla} dimensiones y este modelo "
                         f"produce {vectorizador.dimension}. Vuelve a correr con --recrear.")

    if args.continuar:
        otros = bd.uno(conexion, "SELECT count(*) FROM fragmentos WHERE modelo_embedding <> %s", [nombre_modelo])
        if otros:
            raise SystemExit("La tabla tiene fragmentos de otro modelo. No se pueden mezclar: usa --recrear.")
        cursor.execute("SELECT archivo, orden FROM fragmentos")
        ya = {(a, o) for a, o in cursor.fetchall()}
        antes = len(fragmentos)
        fragmentos = [f for f in fragmentos if (f["archivo"], f["orden"]) not in ya]
        print(f"Ya había {len(ya)} fragmentos; faltan {len(fragmentos)} de {antes}.")
    else:
        cursor.execute("TRUNCATE fragmentos RESTART IDENTITY")
        conexion.commit()

    conocidos = set()
    cursor.execute("SELECT id FROM experimentos")
    conocidos = {f[0] for f in cursor.fetchall()}
    desconocidos = {f["experimento_id"] for f in fragmentos} - conocidos
    if desconocidos:
        raise SystemExit(f"Hay fragmentos de experimentos que no están en la base: {sorted(desconocidos)}. "
                         "Corre: python scripts/cargar_bd.py")

    total, inicio = len(fragmentos), time.time()
    print(f"Cargando {total} fragmentos...")
    for i in range(0, total, args.lote):
        grupo = fragmentos[i:i + args.lote]
        # El nombre del experimento va al inicio para que el vector "sepa" de qué experimento habla.
        try:
            vectores = vectorizador.documentos([f"{f['experimento']}: {f['texto']}" for f in grupo])
        except Exception as e:  # cuota de Gemini agotada, sin conexión, etc.
            raise SystemExit(f"\n{e}\n\nSe detuvo en el fragmento {i} de {total}. Lo ya subido quedó guardado.\n"
                             "Retoma con:  python scripts/cargar_fragmentos.py --continuar")
        filas = [[f["experimento_id"], f["experimento"], f.get("pilar") or None, f.get("doi") or None,
                  f["tipo_documento"], f.get("titulo_documento") or None, f["archivo"], f.get("pagina"),
                  f["orden"], f["texto"].replace("\x00", ""), f.get("tambien_en") or [], nombre_modelo,
                  a_pgvector(v)] for f, v in zip(grupo, vectores)]
        try:
            bd.insertar(conexion, "fragmentos", COLUMNAS, filas, conversiones=CONVERSIONES,
                        al_final="ON CONFLICT (archivo, orden) DO NOTHING", lote=args.lote)
            conexion.commit()
        except Exception as e:
            raise SystemExit(f"\nSe interrumpió la carga en el fragmento {i}: {e}\n"
                             "Lo ya subido quedó guardado. Retoma con:  python scripts/cargar_fragmentos.py --continuar")
        hechos = i + len(grupo)
        transcurrido = time.time() - inicio
        restante = transcurrido / hechos * (total - hechos)
        print(f"   {hechos}/{total}  ({transcurrido / 60:.1f} min; faltan ~{restante / 60:.1f} min)", end="\r")

    en_base = bd.uno(conexion, "SELECT count(*) FROM fragmentos")
    print(f"\nListo: la tabla fragmentos tiene {en_base} fragmentos.")
    print('Prueba la búsqueda con:  python scripts/buscar.py "¿qué son las llamas frías?"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
