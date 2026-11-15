"""Prueba el chat completo (RAG): busca fragmentos en la base y la IA (Gemini o Groq) redacta con citas.

Es exactamente lo que hará el endpoint /chat del backend en la Fase 2.

Necesita en .env:  DATABASE_URL, MODELO_CHAT y la clave de su proveedor (GEMINI_API_KEY o GROQ_API_KEY).
La búsqueda usa el mismo modelo de embeddings con el que se cargaron los fragmentos
(puede ser el local o Gemini; son independientes del modelo que redacta).

Uso:
  python scripts/preguntar.py "¿qué son las llamas frías y por qué importan para la seguridad?"
  python scripts/preguntar.py "how does CO2 affect droplet extinction?" -k 10
  python scripts/preguntar.py "¿qué tan rápido se propaga el fuego en telas?" --experimento PSI-62
  python scripts/preguntar.py "..." --ver-fragmentos      # muestra también lo que se le mandó
  python scripts/preguntar.py "..." --repetir 3 --temperatura 0.5   # compara 3 respuestas seguidas
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bd  # noqa: E402
from buscar import buscar, buscar_por_pilares, con_vecinos, preparar
from fuentes_generales import nombre_fuente  # noqa: E402
from llm import agrupar_fuentes, es_negativa, seguridad_al_reves, fuentes_citadas, numeros_sin_respaldo, quitar_veredictos, responder
from seguridad import revisar_pregunta  # noqa: E402
from idioma import detectar_idioma  # noqa: E402
from escenarios import describir  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Pregunta al chat (RAG + Groq o Gemini).")
    p.add_argument("pregunta")
    p.add_argument("-k", type=int, default=8, help="fragmentos que se le dan al modelo (default 8)")
    p.add_argument("--experimento", default="", help="sólo este experimento (ej. PSI-69)")
    p.add_argument("--pilar", default="", help="prevencion | deteccion | supresion | contexto")
    p.add_argument("--modelo-chat", help="modelo que redacta (default: MODELO_CHAT de .env)")
    p.add_argument("--sin-vecinos", action="store_true", help="no agregar los fragmentos vecinos")
    p.add_argument("--ver-fragmentos", action="store_true", help="mostrar los fragmentos encontrados")
    p.add_argument("--por-pilar", action="store_true",
                   help="buscar por prevención/detección/supresión y responder en 3 viñetas (como el dictamen)")
    p.add_argument("--temperatura", type=float, help="sólo para esta prueba (si no, TEMPERATURA_CHAT de .env)")
    p.add_argument("--repetir", type=int, default=1, help="repetir la misma pregunta N veces para comparar")
    p.add_argument("--pausa", type=int, default=40,
                   help="segundos entre repeticiones, para no pasar el límite por minuto (default 40)")
    p.add_argument("--idioma", choices=["es", "en"], default="es",
                   help="idioma si la pregunta no lo deja claro (si la escribes en inglés, responde en inglés)")
    args = p.parse_args()

    idioma = detectar_idioma(args.pregunta, args.idioma)
    bloqueo = revisar_pregunta(args.pregunta, idioma)
    if bloqueo:  # no se busca ni se manda a la IA
        print(bloqueo[1])
        return 0

    from gemini import ErrorIA
    conexion = bd.conectar()
    vectorizador = preparar(conexion)
    print("Buscando fragmentos en la base...")
    try:
        if args.por_pilar:
            fragmentos = buscar_por_pilares(conexion, vectorizador, args.pregunta, max(args.k, 9))
        else:
            fragmentos = buscar(conexion, vectorizador, args.pregunta, args.k, args.experimento, args.pilar)
    except ErrorIA as e:
        raise SystemExit(f"Error al vectorizar la pregunta:\n{e}")
    if not args.sin_vecinos:
        fragmentos = con_vecinos(conexion, fragmentos, tabla=vectorizador.tabla)

    if args.ver_fragmentos:
        print("Fragmentos encontrados:")
        for n, f in enumerate(fragmentos, 1):
            print(f"  [{n}] {f['similitud']:.3f} {f.get('via', ''):11} {nombre_fuente(f)}  {f['archivo']}  "
                  f"{f['texto'][:110].replace(chr(10), ' ')}...")
        print()

    from bd import leer_env
    from llm import temperatura_configurada
    modelo_chat = args.modelo_chat or leer_env().get("MODELO_CHAT") or "gemini-flash-latest"
    temperatura = temperatura_configurada(args.temperatura)
    t = "la del proveedor" if temperatura is None else temperatura
    resumen = []
    for vuelta in range(1, max(1, args.repetir) + 1):
        if vuelta > 1:
            print(f"\n(esperando {args.pausa} s por el límite por minuto...)")
            time.sleep(args.pausa)
        encabezado = f" — vuelta {vuelta} de {args.repetir}" if args.repetir > 1 else ""
        print(f"Preguntando a la IA ({modelo_chat}, temperatura: {t}){encabezado}...\n")
        inicio = time.time()
        escenarios: list[dict] = []
        try:
            texto = responder(args.pregunta, fragmentos, modelo_chat, temperatura=args.temperatura,
                              por_pilar=args.por_pilar, idioma=idioma, escenarios=escenarios)
        except ErrorIA as e:
            raise SystemExit(f"Error al pedir la respuesta a la IA:\n{e}")
        segundos = time.time() - inicio
        texto, quitadas = quitar_veredictos(texto, args.pregunta, idioma)

        print(texto)
        if quitadas:
            print("\nAVISO: se quitaron conclusiones no verificables sobre si el escenario es inflamable o seguro:")
            for q in quitadas:
                print(f"  - {q[:160]}")
        if escenarios and not es_negativa(texto):
            print("\nEscenarios que la IA propone probar en el simulador:")
            for e in escenarios:
                print(f"  - {e['nombre'] or 'sin nombre'}: {describir(e, idioma)}")
        if seguridad_al_reves(texto):
            print("\nAVISO: la línea 'Para la seguridad' recomienda mantener una llama; ignórala.")
        dudosas = numeros_sin_respaldo(texto, fragmentos, args.pregunta)
        if dudosas:
            print(f"\nAVISO: estas cifras no aparecen en los fragmentos consultados: {', '.join(dudosas)}")
        citadas = agrupar_fuentes(fuentes_citadas(texto, fragmentos))
        if citadas:
            print("\nFuentes:")
            for numeros, f in citadas:
                pagina = f", pág. {f['pagina']}" if f.get("pagina") else ""
                doi = f"  doi:{f['doi']}" if f.get("doi") else ""
                etiqueta = "".join(f"[{n}]" for n in numeros)
                print(f"  {etiqueta} {nombre_fuente(f)} — {f.get('titulo_documento') or f['archivo']}{pagina}{doi}")
        elif not es_negativa(texto):
            print("\n(La respuesta no citó fragmentos: tómala con cuidado.)")
        resumen.append((vuelta, len(texto.split()), len(citadas),
                        len({f["experimento_id"] for _, f in citadas if not f.get("fuente_general")}),
                        len(dudosas), segundos))

    if len(resumen) > 1:
        print("\nRESUMEN (para comparar):")
        print("  vuelta  palabras  fuentes  experimentos  cifras_sin_respaldo  segundos")
        for v, palabras, fuentes, exps, dudas, seg in resumen:
            print(f"  {v:>6}  {palabras:>8}  {fuentes:>7}  {exps:>12}  {dudas:>19}  {seg:>8.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
