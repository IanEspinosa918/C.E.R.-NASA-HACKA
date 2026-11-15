"""Redacta la respuesta del chat con Gemini a partir de los fragmentos que encontró el RAG.

El backend (Fase 2) usará responder() igual que preguntar.py.
Modelo: MODELO_CHAT en .env (por defecto gemini-flash-latest = el Flash más reciente).
Razonamiento: NIVEL_RAZONAMIENTO en .env (minimal | low | medium | high; por defecto low,
que responde rápido). Si el modelo no lo acepta, pon NIVEL_RAZONAMIENTO=ninguno.
Necesita GEMINI_API_KEY en .env.

Reglas que se le dan al modelo:
  - contestar SOLO con lo que dicen los fragmentos y citar cada dato con [n];
  - si los fragmentos no alcanzan, decirlo (no inventar);
  - no inventar números: los datos de pruebas salen de la tabla `pruebas` (SQL), no de aquí;
  - recordar que PSI no tiene datos de gravedad parcial (Luna/Marte) cuando se pregunte por eso.
"""

from __future__ import annotations

MODELO_CHAT_POR_DEFECTO = "gemini-flash-latest"

INSTRUCCIONES = """Eres el asistente de un tablero de seguridad contra incendios para misiones espaciales \
(reto "Flame in Freefall", NASA Space Apps). Respondes preguntas sobre experimentos de combustión en \
microgravedad del repositorio NASA PSI (Physical Sciences Informatics).

Reglas:
1. Empieza respondiendo directo a la pregunta (por ejemplo, una definición en 1 o 2 oraciones).
2. Usa SOLO la información de los fragmentos numerados. Cada afirmación que venga de un fragmento \
lleva su número entre corchetes, por ejemplo [2] o [1][3].
3. Pon [n] únicamente si ese fragmento dice eso. Nunca cites un fragmento para algo que no dice, ni \
para estas reglas o notas generales.
4. Si los fragmentos no bastan, dilo claramente y sugiere qué experimento podría tener la respuesta.
5. No inventes cifras. Si das un número, debe estar en un fragmento citado, con sus unidades.
6. Relaciona con prevención, detección o supresión SOLO si los fragmentos lo apoyan. Si es una \
deducción tuya, escríbela aparte empezando con "Interpretación:" y sin cita. No exageres: que un \
instrumento de laboratorio no viera algo no significa que un detector de humo de una nave falle.
7. SOLO si la pregunta menciona la Luna, Marte, gravedad parcial o bases lunares: aclara que PSI no \
tiene datos de gravedad parcial (sólo microgravedad y gravedad normal), sin cita.
8. Responde en el idioma de la pregunta, claro para un público no especialista, en unas 150 a 250 \
palabras salvo que pidan más detalle."""


def armar_contexto(fragmentos: list[dict]) -> str:
    bloques = []
    for n, f in enumerate(fragmentos, 1):
        origen = f"{f['experimento']} ({f['experimento_id']})"
        documento = f.get("titulo_documento") or f.get("archivo") or ""
        pagina = f", pág. {f['pagina']}" if f.get("pagina") else ""
        bloques.append(f"[{n}] {origen} — {f.get('tipo_documento', '')}: {documento}{pagina}\n{f['texto']}")
    return "\n\n".join(bloques)


ESTILOS = {
    "engineer": "Responde para un ingeniero de sistemas de la NASA: técnico, preciso y orientado a "
                "decisiones de diseño (qué implica para prevención, detección y supresión).",
    "student": "Responde para estudiantes y público general: lenguaje sencillo, con una analogía si ayuda.",
}


def responder(pregunta: str, fragmentos: list[dict], modelo: str | None = None,
              contexto: str = "", estilo: str = "") -> str:
    """Manda la pregunta + fragmentos a Gemini y regresa el texto de la respuesta.
    `contexto`: escenario que el usuario está viendo en el tablero (no es fuente, no se cita).
    `estilo`: "engineer" o "student" (perfil del público)."""
    from bd import leer_env
    from gemini import ErrorGemini, llamar

    modelo = (modelo or leer_env().get("MODELO_CHAT") or MODELO_CHAT_POR_DEFECTO).replace("models/", "")
    if not fragmentos:
        return "No encontré fragmentos relacionados con esa pregunta en la base."
    cuerpo = {
        "systemInstruction": {"parts": [{"text": INSTRUCCIONES}]},
        "contents": [{"role": "user", "parts": [{"text":
            mensaje_usuario(pregunta, fragmentos, contexto, estilo)}]}],
        # Sin temperature/top_p/top_k: los modelos Gemini nuevos ya no los aceptan.
    }
    # "Razonamiento" interno: más alto = más lento. Para resumir fragmentos basta "low".
    nivel = (leer_env().get("NIVEL_RAZONAMIENTO") or "low").strip().lower()
    if nivel not in ("", "ninguno", "default"):
        cuerpo["generationConfig"] = {"thinkingConfig": {"thinkingLevel": nivel}}
    respuesta = llamar(f"models/{modelo}:generateContent", cuerpo)

    candidatos = respuesta.get("candidates") or []
    if not candidatos:
        motivo = (respuesta.get("promptFeedback") or {}).get("blockReason", "sin motivo")
        raise ErrorGemini(f"Gemini no generó respuesta (bloqueo: {motivo}).")
    partes = (candidatos[0].get("content") or {}).get("parts") or []
    texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
    if not texto.strip():
        raise ErrorGemini(f"Gemini regresó una respuesta vacía (finishReason: {candidatos[0].get('finishReason')}).")
    return texto.strip()


def mensaje_usuario(pregunta: str, fragmentos: list[dict], contexto: str = "", estilo: str = "") -> str:
    partes = [f"Fragmentos:\n\n{armar_contexto(fragmentos)}", "---"]
    if contexto:
        partes.append("Escenario que el usuario está analizando en el tablero (dato del usuario, NO es una "
                      f"fuente: no lo cites con [n]):\n{contexto}")
    if estilo in ESTILOS:
        partes.append(f"Público: {ESTILOS[estilo]}")
    partes.append(f"Pregunta: {pregunta}")
    return "\n\n".join(partes)


def fuentes_citadas(texto: str, fragmentos: list[dict]) -> list[tuple[int, dict]]:
    """Fragmentos que la respuesta realmente citó con [n], en orden."""
    import re
    usados = sorted({int(n) for n in re.findall(r"\[(\d+)\]", texto) if 1 <= int(n) <= len(fragmentos)})
    return [(n, fragmentos[n - 1]) for n in usados]
