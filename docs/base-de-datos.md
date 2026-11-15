# Base de datos y RAG

Una sola base **Postgres con pgvector** guarda todo. El esquema está en
[`backend/esquema.sql`](../backend/esquema.sql).

| Tabla | Contenido | La usan |
|---|---|---|
| `experimentos` | Los 24 experimentos: nombre, pilar, equipo, DOI, objetivo, publicaciones | Dashboard, filtros |
| `pruebas` | Las pruebas limpias (mismas columnas que `data/processed/pruebas.csv`) | Gráficas, simuladores, exportar CSV, números exactos para la IA |
| `fragmentos` | Pedazos de texto de fichas y documentos, con su vector y metadatos | Chat con IA (RAG) |
| `experimentos_resumen` (vista) | Cada experimento con su número de pruebas y rangos de O₂ y presión | Tarjetas del dashboard |

## Puesta en marcha (una sola persona del equipo)

### 1. Crear la base (Supabase, gratis)
1. Crea una cuenta y un proyecto en https://supabase.com. Guarda la **contraseña de la base**
   (usa una sin símbolos como `@ # / :` para evitar problemas).
2. En el proyecto, botón **Connect** (arriba) → **Session pooler** → copia la dirección.
   Se ve así: `postgresql://postgres.abcd1234:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres`
3. En la carpeta del proyecto copia `.env.example`, nómbralo `.env`, y pega la dirección en
   `DATABASE_URL` cambiando `[YOUR-PASSWORD]` por tu contraseña.

El archivo `.env` **no se sube a GitHub**. Para que el equipo se conecte, pásales la dirección
por un canal privado (no la pongan en el repositorio ni en el chat público).

También funciona con Neon o con un Postgres 15+ local que tenga pgvector: sólo cambia `DATABASE_URL`.

### 2. Cargar los datos
```powershell
pip install -r requirements.txt
python scripts\cargar_bd.py            # experimentos + pruebas (segundos)
python scripts\preparar_textos.py      # extrae los textos (unos minutos)
python scripts\cargar_fragmentos.py    # vectores + subida (10 a 30 min; descarga el modelo la 1ª vez)
python scripts\buscar.py "¿qué son las llamas frías?"
```
- `python scripts\cargar_bd.py --revisar` muestra qué hay en la base sin cambiar nada.
- Si la carga de fragmentos se interrumpe: `python scripts\cargar_fragmentos.py --continuar`.
- Cuando cambie `pruebas.csv` (una limpieza nueva), basta volver a correr `cargar_bd.py`;
  no toca los fragmentos.

## Cómo funciona el RAG

```
PREPARAR (una vez)     documentos -> fragmentos de ~500 caracteres -> vector -> tabla fragmentos
BUSCAR (cada pregunta) pregunta -> vector -> Postgres regresa los fragmentos más parecidos
RESPONDER (backend)    fragmentos + pregunta -> modelo de IA -> respuesta con citas (experimento + DOI)
```

Cada fragmento guarda sus **metadatos**: `experimento_id`, `experimento`, `pilar`, `doi`,
`tipo_documento` (ficha, reporte, documento_cientifico, presentacion), `titulo_documento`,
`archivo`, `pagina` y `orden`. Con eso el chat cita la fuente y se puede filtrar antes de buscar
(por ejemplo, sólo `pilar = 'supresion'` cuando el usuario está en ese simulador).

Consulta de ejemplo (la misma que hace `scripts/buscar.py`):
```sql
SELECT experimento, doi, titulo_documento, pagina, texto,
       1 - (embedding <=> $1::vector) AS similitud
FROM fragmentos
WHERE experimento_id = 'PSI-69' OR 'PSI-69' = ANY(tambien_en)   -- filtro opcional
ORDER BY embedding <=> $1::vector
LIMIT 5;
```

### Reglas para el backend
- **Mismo modelo para preguntas y documentos.** Los vectores se calculan con el modelo de
  `MODELO_EMBEDDINGS` (por defecto `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensiones,
  local y gratuito). El backend debe vectorizar las preguntas con ese mismo modelo:
  puede importar `Vectorizador` de `scripts/embeddings.py` y `buscar()` de `scripts/buscar.py`.
- **Los números no salen del RAG.** "¿Cuántas pruebas de FLEX se apagaron con más de 20 % de
  CO₂?" se responde con SQL sobre `pruebas`, no con fragmentos de texto.
- **Fragmentos vecinos.** Los fragmentos son cortos; para dar más contexto al modelo de IA
  se pueden traer también los de `orden ± 1` del mismo `archivo`.
- **Documentos compartidos.** Un mismo archivo puede venir en varios experimentos (ej. los de
  ACME). Se guarda una vez y los demás quedan en `tambien_en`.
- **Citar siempre** `experimento` y `doi`.

### Cómo se buscan los fragmentos
`scripts/buscar.py` hace búsqueda **híbrida**:
- por significado (vectores, cruza español-inglés);
- por palabras clave (texto completo de Postgres, índice `fragmentos_texto_idx`);
- se combinan con Reciprocal Rank Fusion.

Como los documentos están en inglés, `scripts/glosario.py` traduce los términos técnicos de la
pregunta (por ejemplo, "llamas frías" → "cool flame"). Si una pregunta no encuentra lo que
debería, agrega el término al glosario.

Después se eligen fragmentos variados:
- sin casi-duplicados;
- máximo 2 por documento y 4 por experimento.

Para comparar: `python scripts\buscar.py "..." --solo-vectores --sin-diversidad`.

### Cambiar de modelo de embeddings
Cambia `MODELO_EMBEDDINGS` en `.env` y vuelve a cargar con
`python scripts\cargar_fragmentos.py --recrear` (la tabla depende del tamaño del vector).
Modelos locales compatibles: los que lista `fastembed` (ej.
`sentence-transformers/paraphrase-multilingual-mpnet-base-v2`, más preciso y más pesado).

La base guarda en `modelo_embedding` el nombre exacto con el que se cargó; los scripts se
niegan a buscar con otro modelo para que nunca se mezclen vectores incompatibles.

## Groq (chat)

El chat puede usar Groq en lugar de Gemini. Groq **sólo redacta** las respuestas; la búsqueda
sigue con el modelo de embeddings de siempre, así que no hay que recargar nada.

1. Crea la clave en <https://console.groq.com/keys> y ponla **sólo** en `.env`:
   `GROQ_API_KEY=gsk_...`
2. En `.env`: `MODELO_CHAT=openai/gpt-oss-120b` (o `openai/gpt-oss-20b`, más rápido) y
   `NIVEL_RAZONAMIENTO=low`.
3. Revisa la conexión y los modelos disponibles: `python scripts\probar_groq.py`.
4. Prueba: `python scripts\preguntar.py "¿qué son las llamas frías?"` o reinicia el backend.

Límites del plan gratis: son por modelo y por organización. Para `openai/gpt-oss-120b`, Groq
publica 30 peticiones por minuto, 1,000 al día, 8,000 tokens por minuto y 200,000 al día. Cada
pregunta del chat gasta unos 3,000 a 5,000 tokens (fragmentos + respuesta), así que alcanza para
unas 40 a 60 preguntas al día y 1 o 2 por minuto. Los límites exactos de tu cuenta aparecen en tu consola de
Groq (<https://console.groq.com>).

Para volver a Gemini basta con poner un modelo `gemini-...` en `MODELO_CHAT`.

## Gemini (API de Google)

Se usa para dos cosas independientes:

| Para qué | Variable en `.env` | Valor |
|---|---|---|
| Vectores de los fragmentos (opcional) | `MODELO_EMBEDDINGS` | `gemini-embedding-001` |
| | `DIMENSIONES_EMBEDDINGS` | `768` (o `1536`; no más de 2000 por el índice de pgvector) |
| Redactar las respuestas del chat | `MODELO_CHAT` | `gemini-flash-latest` (por defecto) |
| | `NIVEL_RAZONAMIENTO` | `low` (por defecto; `minimal` es más rápido, `high` más lento) |
| Ambas | `GEMINI_API_KEY` | tu clave |

1. Saca la clave en <https://aistudio.google.com> → **Get API key** → **Create API key**.
   Pégala **sólo** en `.env` (nunca en el chat, WhatsApp ni GitHub). Cada quien puede usar su
   propia clave.
2. Revisa la conexión y la clave: `python scripts\probar_gemini.py`.
   Prueba el chat completo (funciona con los vectores locales que ya están cargados):
   `python scripts\preguntar.py "¿qué son las llamas frías?"`
3. (Opcional) Pasar también los vectores a Gemini: primero una prueba chica
   `python scripts\cargar_fragmentos.py --recrear --limite 200` y luego
   `python scripts\buscar.py "..."`. Si convence, carga todo con `--recrear` sin `--limite`.

Notas:
- **Límites del plan gratuito.** Son por proyecto de Google (no por clave) y la cuota diaria se
  reinicia a medianoche hora del Pacífico. Si se alcanza el límite por minuto, el script espera
  solo; si se acaba la cuota del día, se detiene y se retoma otro día con `--continuar`. Los
  límites exactos de tu cuenta están en <https://aistudio.google.com/rate-limit>.
- **Volver al modelo local:** borra o cambia `MODELO_EMBEDDINGS` en `.env` y corre
  `cargar_fragmentos.py --recrear`.
- En el plan gratuito Google puede usar lo que se envía para mejorar sus productos. Aquí sólo
  van textos públicos de la NASA y las preguntas del chat; no mandes datos personales.
- `scripts/gemini.py` hace las llamadas (REST, sin librerías extra), `scripts/llm.py` arma el
  mensaje con los fragmentos numerados y pide citar cada dato con `[n]`; `preguntar.py` muestra
  la respuesta y las fuentes citadas (experimento, documento, página y DOI).

## Qué entra y qué no entra a `fragmentos`
- Entra: la ficha de cada experimento y los documentos de *Reports*, *Science Documents* y
  *Presentations* en `.pdf`, `.docx` y `.pptx`.
- No entra: *Engineering Documents* (planos y procedimientos; opción `--con-ingenieria`),
  formatos antiguos (`.doc`, `.ppt`, `.xls`), `.zip`, videos, PDFs escaneados sin texto y
  archivos repetidos. El reporte `data/reportes/textos_<fecha>.csv` lista cada archivo y por qué.

## Seguridad
- Las tres tablas tienen seguridad por filas (RLS) con una política de **sólo lectura**: en
  Supabase, quien tenga la clave pública puede leer (son datos públicos de la NASA) pero no
  modificar ni borrar. El backend y los scripts se conectan como dueños y sí pueden escribir.
- La contraseña de la base y las claves de Gemini y Groq sólo viven en `.env`.
