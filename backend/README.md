# Backend

API del tablero (FastAPI) en [`app.py`](app.py). También sirve la página de `frontend/`.

## Arrancar

```
pip install -r requirements.txt
python backend\app.py
```

Abre <http://127.0.0.1:8000> (la página) o <http://127.0.0.1:8000/docs> (para probar la API).
Para que otras compus de tu red lo vean: `python backend\app.py --host 0.0.0.0`.

Usa el mismo `.env` que los scripts: `DATABASE_URL`, `MODELO_EMBEDDINGS`, `GEMINI_API_KEY`,
`MODELO_CHAT`, `NIVEL_RAZONAMIENTO`. La clave de Gemini se queda en el servidor; la página
nunca la ve.

## Endpoints

| Método | Ruta | Qué regresa |
|---|---|---|
| GET | `/api/salud` | Estado: experimentos, fragmentos, modelos y si Gemini está configurado |
| GET | `/api/experimentos` | Los 24 experimentos (pilar, combustible, DOI, número de pruebas…) |
| GET | `/api/pruebas?experimento_id=PSI-69&resultado=&limite=200` | Pruebas limpias (los números exactos salen de aquí, no del chat) |
| POST | `/api/chat` | Respuesta del chat con sus fuentes |

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
  "vecinos": true
}
```

Respuesta: `respuesta` (texto con citas `[n]`), `fuentes` (n, experimento, documento, página,
DOI y enlace), `modelo`, `fragmentos_usados` y `segundos`.

## Cómo funciona `/api/chat`

1. Busca los fragmentos más parecidos a la pregunta en Postgres (`scripts/buscar.py`) y les
   agrega los fragmentos vecinos para dar contexto.
2. Gemini redacta la respuesta con reglas estrictas: solo usa los fragmentos, cita cada dato
   y marca como "Interpretación:" lo que deduce (`scripts/llm.py`).
3. Regresa solo las fuentes que la respuesta citó.

Cambiar de modelo de chat = cambiar `MODELO_CHAT` en `.env` (o mandar `"modelo"` en la
petición). La página no se toca.

## Pendiente
- Búsqueda híbrida (significado + palabras clave).
- Respuestas numéricas con SQL sobre `pruebas` (function calling).
- `/export.csv` y controlar los simuladores desde el chat.
