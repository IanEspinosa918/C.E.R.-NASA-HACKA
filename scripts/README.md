# Scripts de datos

Orden de uso:

```powershell
pip install -r requirements.txt       # 0. librerías (una sola vez)
python scripts\descargar_psi.py       # 1. descarga de PSI a data\raw\
python scripts\limpiar_todo.py        # 2. limpia todo a data\processed\pruebas.csv
python scripts\cargar_bd.py           # 3. sube experimentos y pruebas a Postgres
python scripts\preparar_textos.py     # 4. extrae y parte los textos para el chat
python scripts\cargar_fragmentos.py   # 5. calcula los vectores y los sube a Postgres
python scripts\buscar.py "¿qué son las llamas frías?"   # 6. prueba la búsqueda
python scripts\preguntar.py "¿qué son las llamas frías?" # 7. chat completo (Groq o Gemini)
```

Los pasos 3, 5, 6 y 7 necesitan la base de datos (el 7 además la clave de Groq o Gemini): ver [`docs/base-de-datos.md`](../docs/base-de-datos.md).

| Script | Qué hace |
|---|---|
| `descargar_psi.py` | Descarga fichas, tablas y documentos de PSI |
| `limpiar_todo.py` | Corre todas las limpiezas y junta el resultado en `data/processed/pruebas.csv` |
| `limpiar_flex.py`, `limpiar_bass2.py`, `limpiar_cfi.py`, `limpiar_saffire.py`, `limpiar_same.py` | Limpian cada experimento → `data/processed/pruebas_<nombre>.csv` |
| `comun_limpieza.py` | Formato común, lectura de valores sucios y validación (lo usan los `limpiar_*`) |
| `investigaciones.py` | Lista de los 24 experimentos y su clasificación (pilar, combustible, equipo) |
| `cargar_bd.py` | Crea las tablas `experimentos` y `pruebas` y carga los datos (`--revisar` muestra qué hay) |
| `preparar_textos.py` | Fichas + PDF/docx/pptx → `data/processed/fragmentos.jsonl` con metadatos |
| `cargar_fragmentos.py` | Embeddings de los fragmentos → tabla `fragmentos` (pgvector) |
| `buscar.py` | Prueba la búsqueda del RAG; su función `buscar()` la puede usar el backend |
| `preguntar.py` | Chat completo: busca fragmentos y la IA (Gemini o Groq) responde citando experimento y DOI |
| `bd.py`, `embeddings.py` | Conexión a Postgres y modelo de embeddings, local o Gemini (compartidos) |
| `glosario.py` | Términos español→inglés para la búsqueda por palabras clave |
| `gemini.py`, `groq_api.py`, `llm.py` | Llamadas a Gemini y a Groq (con reintentos) y armado de la respuesta del chat |
| `probar_gemini.py`, `probar_groq.py` | Revisan la clave y la conexión con cada proveedor |

El formato de la tabla limpia está en [`docs/formato-datos.md`](../docs/formato-datos.md).
Cada limpieza deja un reporte de problemas en `data/reportes/validacion_<nombre>.csv`.

## `descargar_psi.py`: descarga los datos de NASA PSI

Baja los 24 experimentos de `investigaciones.py` a `data/raw/`. Por cada experimento
guarda la ficha (`ficha.json`), la lista completa de archivos (`listado_archivos.json`)
y los archivos de cada categoría. **Nunca baja Raw Data** (son terabytes).

No necesita instalar nada además de Python 3.8 o más reciente.

### Requisito: Python

En una terminal (PowerShell):

```powershell
python --version
```

Si no aparece una versión, instálalo desde https://www.python.org/downloads/ y en el
instalador **marca la casilla "Add python.exe to PATH"**. Cierra y vuelve a abrir la terminal.
En Windows también puede funcionar `py` en lugar de `python`.

### Pasos

```powershell
cd C:\Users\ianda\HackatonNASA

# 1. Ver qué se va a bajar y cuánto pesa (no descarga nada)
python scripts\descargar_psi.py --solo-listar

# 2. Descarga rápida: solo fichas y tablas CSV (unos minutos, pocos MB)
python scripts\descargar_psi.py --solo-tablas

# 3. Descarga normal: fichas, tablas y documentos (PDF, presentaciones, etc.)
python scripts\descargar_psi.py
```

### Opciones

| Opción | Qué hace |
|---|---|
| `--solo-listar` | No descarga; muestra qué bajaría y cuánto pesa |
| `--solo-tablas` | Solo fichas, CSV y metadatos |
| `--todo` | Incluye además Analyzed Data, Reference Data y Calibration (~2 GB más) |
| `--ids PSI-69 PSI-26` | Solo esos experimentos |
| `--max-mb 100` | Salta archivos de más de 100 MB (default: 300; `0` = sin límite) |
| `--hilos 4` | Descargas simultáneas (default: 4) |

### Qué queda después

```
data/raw/
├── indice.csv                 ← un renglón por experimento, con su DOI
├── PSI-69_FLEX/
│   ├── ficha.json
│   ├── listado_archivos.json
│   ├── Experimental table/    ← el CSV de pruebas
│   ├── Science Documents/
│   ├── Presentations/
│   └── Engineering Documents/
└── ...
data/reportes/descarga_<fecha>.csv  ← qué se bajó, qué se saltó y por qué, y qué falló
```

### Si algo falla

- **Vuelve a correr el mismo comando.** Lo que ya se descargó completo no se vuelve a bajar.
- Revisa el reporte en `data/reportes/` para ver qué falló.
- El script usa la API interna de la página de PSI (no es una API pública documentada).
  Si PSI cambia su página, puede dejar de funcionar.
- Los datos **no se suben a GitHub** (`data/` está en `.gitignore`). Cada integrante corre
  el script, o se comparte la carpeta `data/raw/` por Drive.
