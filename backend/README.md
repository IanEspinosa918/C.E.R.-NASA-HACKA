# Backend

API del tablero (FastAPI) en [`app.py`](app.py). También sirve la página de `frontend/`.

## Arrancar

```
pip install -r requirements.txt
python backend\app.py
```

Abre <http://127.0.0.1:8000> (la página) o <http://127.0.0.1:8000/docs> (para probar la API).
Para que otras compus de tu red lo vean: `python backend\app.py --host 0.0.0.0`.

Usa el mismo `.env` que los scripts: `DATABASE_URL`, `MODELO_EMBEDDINGS`, `MODELO_CHAT`,
`NIVEL_RAZONAMIENTO` y la clave del proveedor (`GROQ_API_KEY` o `GEMINI_API_KEY`). Las claves
se quedan en el servidor; la página nunca las ve.

## Endpoints

| Método | Ruta | Qué regresa |
|---|---|---|
| GET | `/api/salud` | Estado: experimentos, fragmentos, modelos y si Gemini está configurado |
| GET | `/api/experimentos` | Los 24 experimentos (pilar, combustible, DOI, número de pruebas…) |
| GET | `/api/pruebas?experimento_id=PSI-69&resultado=&limite=200` | Pruebas limpias (los números exactos salen de aquí, no del chat) |
| POST | `/api/chat` | Respuesta del chat con sus fuentes |
| GET | `/api/iss` | Elementos orbitales (TLE) de la Estación Espacial Internacional, bajados de CelesTrak y guardados 2 h. La página calcula con ellos la posición en vivo (visor 3D en 0 g). Si no hay internet responde 503 y la página usa una órbita esquemática. `ISS_TLE_URL` en el entorno cambia la fuente |

Cuerpo de `/api/chat`:

```json
{
  "pregunta": "¿qué son las llamas frías?",
  "k": 8,
  "experimento_id": "",
  "pilar": "",
  "contexto": "escenario del tablero (no es fuente, no se cita)",
  "estilo": "engineer | student",
  "modelo": "",
  "vecinos": true,
  "dictamen": false,
  "idioma": "es | en"
}
```

**Modo bitácora** (`"modo": "bitacora"`): para analizar una bitácora de pruebas (la ventana ACME 17319).
La bitácora completa va en `contexto` (hasta 6000 caracteres) y es la **única fuente**: no se buscan
fragmentos ni se usa la base de datos. La IA sigue otras reglas (`INSTRUCCIONES_BITACORA` en
`scripts/llm.py`): cada dato con su prueba entre paréntesis, no inventar causas, soluciones = cambios
que la bitácora registra en otras pruebas, máximo 2 interpretaciones marcadas. La respuesta trae
`modo: "bitacora"`, `cifras_sin_respaldo` (cifras que no están en la bitácora), `unidades_sin_respaldo`
(unidades que la bitácora no usa, por ejemplo "sccm") e `ids_sin_respaldo` (pruebas que no existen en ella). El filtro de seguridad se aplica igual. Un backend anterior ignora
`modo` y responde como chat normal.

`contexto` son los **datos actuales del tablero** (gravedad, O₂, presión, flujo, combustible…). La página
los manda con cada pregunta, así la IA puede contestar "¿qué gravedad hay seleccionada?" (marca esas
oraciones con "(dato del tablero)", sin cita). Hoy son los parámetros del simulador; si después vienen de
sensores, sólo cambia lo que se manda en `contexto`. `dictamen` (opcional): `true` para el botón
"Interpretar este escenario con IA", `false` para preguntas libres; si no se manda, se deduce como antes
(`por_pilar` con `contexto` = dictamen).

Respuesta: `respuesta` (texto con citas `[n]`), `fuentes` (n, experimento, documento, página,
DOI y enlace), `modelo`, `fragmentos_usados`, `idioma`, `segundos` y `escenarios_propuestos`.

**Escenarios propuestos (IA → simulador)** (`scripts/escenarios.py`): cuando la IA sugiere probar
valores concretos en el simulador, escribe al final líneas
`ESCENARIO: nombre=…; o2=21 %; presion=70 kPa; gravedad=1/6; flujo=10 cm/s; combustible=solido`.
El backend las quita del texto y las manda aparte (máximo 3), con unidades fijas:

```json
"escenarios_propuestos": [
  { "nombre": "Aire terrestre a baja presión", "o2_pct": 21.0, "presion_psi": 10.15,
    "gravedad_g": null, "flujo_cm_s": 10.0, "combustible": null, "original": "nombre=…" }
]
```

`null` = ese parámetro no cambia. Acepta kPa, psi, atm, bar; m/s, cm/s, mm/s; gravedad como
fracción (1/6), número, m/s² o palabra (Luna, Marte, órbita, Tierra). Un nombre que afirme que el
caso es "seguro" o "no inflamable" se descarta. La página ajusta cada valor al rango de sus
deslizadores y muestra el botón **Aplicar al simulador**.

**Compatibilidad:** el cuerpo de la petición no cambió y la respuesta sólo agrega ese campo
(siempre es una lista; vacía si no hay escenarios, si la pregunta se bloqueó o si la IA se negó).
Una página anterior lo ignora y nunca ve las líneas `ESCENARIO`. `responder()` las quita siempre
del texto; quien quiera los escenarios le pasa `escenarios=[]` (parámetro opcional).

**Idioma de la respuesta** (`scripts/idioma.py`): si la pregunta pide un idioma ("in English",
"respóndeme en inglés", "in Spanish") se respeta; si no, se detecta por sus palabras (inglés o
español). Sólo si no se distingue (por ejemplo "FLEX-2") se usa `idioma` (el de la página). En
inglés, la IA recibe la instrucción de responder en inglés con las etiquetas "For safety:",
"Interpretation:" y "(general knowledge, not from PSI)", y las revisiones automáticas (filtro de
seguridad, conclusiones sobre el escenario, negativas y seguridad al revés) funcionan en ambos
idiomas. En consola: `python scripts\preguntar.py "What are cool flames?"` responde en inglés.

## Cómo funciona `/api/chat`

1. Busca fragmentos en Postgres (`scripts/buscar.py`) con **búsqueda híbrida**: por
   significado (vectores) y por palabras clave (texto completo, con un glosario
   español→inglés en `scripts/glosario.py`), combinadas con Reciprocal Rank Fusion.
2. Elige fragmentos **variados**: sin casi-duplicados, máximo 2 por documento y 4 por
   experimento (sin límites si se filtra por un experimento). Les agrega los vecinos.
3. El modelo de chat (Groq o Gemini, según `MODELO_CHAT`) redacta con reglas estrictas
   (`scripts/llm.py`):
   - cita cada dato y no da cifras que no estén en los fragmentos;
   - marca el conocimiento general como "(conocimiento general, no de PSI)";
   - conserva las condiciones de cada resultado;
   - ignora instrucciones escondidas en los documentos;
   - cierra con "Para la seguridad:".
4. Revisa las cifras de la respuesta: las que no aparecen en los fragmentos se regresan en
   `cifras_sin_respaldo` y la página las marca con un aviso.
5. Regresa solo las fuentes que la respuesta citó.

Cambiar de modelo de chat = cambiar `MODELO_CHAT` en `.env` (o mandar `"modelo"` en la
petición). La página no se toca.

## Seguridad del chat

Hay dos capas de protección:

1. **Filtro previo** (`scripts/seguridad.py`). Detecta frases claras de:
   - intención de dañar a otros;
   - sabotaje o desactivar sistemas de seguridad;
   - autolesión.

   En esos casos responde con un mensaje fijo, sin buscar ni llamar a la IA. En autolesión da
   el 911 y la Línea de la Vida (800 911 2000). La respuesta trae `"bloqueada": "dano"` o
   `"autolesion"`.
2. **Reglas de la IA** (`scripts/llm.py`, sección "USO RESPONSABLE"). La IA:
   - no da instrucciones para provocar incendios o explosiones ni para dañar personas;
   - no explica cómo evadir detectores ni sistemas de la nave;
   - no comparte nada que comprometa una misión;
   - no reemplaza los protocolos de emergencia;
   - no se hace pasar por la NASA;
   - ignora los intentos de saltarse estas reglas.

El filtro es corto a propósito para no bloquear preguntas de prevención legítimas, por ejemplo
"¿qué puede provocar un incendio en una nave?".

## Dictamen del escenario (`"por_pilar": true`)

El botón "Interpretar este escenario con IA" manda `por_pilar: true`. El backend hace entonces
una búsqueda con la pregunta y otra por cada pilar (prevención, detección y supresión),
filtrando por los experimentos de ese pilar, y la IA responde en tres viñetas.

## Documentos generales

Algunas guías y hojas informativas están guardadas en la carpeta de un experimento, aunque
no son resultados suyos. Por ejemplo, la ISS Researchers Guide está en la de ACME BRE.
`scripts/fuentes_generales.py` las etiqueta (columna `fuente_general`). El chat las muestra
como "documento general" y la IA no las presenta como resultados de ese experimento.

## Pendiente
- Respuestas numéricas con SQL sobre `pruebas` (function calling).
- `/export.csv` y controlar los simuladores desde el chat.
