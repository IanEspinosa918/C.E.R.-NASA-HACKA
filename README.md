# C.E.R. NASA Hacka

Proyecto del equipo para **NASA Space Apps Challenge 2026**, reto
[Flame in Freefall](https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=details):
un dashboard web con IA que resume, ordena e interpreta los experimentos de combustión
en microgravedad de la NASA (repositorio PSI) para dar información de seguridad contra
incendios en naves, estaciones, bases lunares y vehículos presurizados.

## Estructura

```
HackatonNASA/
├── README.md              ← este archivo
├── .gitignore
├── docs/                  ← documentación del equipo
│   ├── reto.md            ← qué pide el reto + checklist
│   ├── plan.md            ← fases de trabajo e ideas para después
│   ├── fuentes.md         ← los 24 experimentos de PSI y otras fuentes
│   └── trampas-datos.md   ← problemas conocidos en los datos
├── scripts/               ← scripts de datos (descarga, limpieza, validación)
│   ├── investigaciones.py ← lista de los 24 experimentos
│   └── descargar_psi.py   ← descarga fichas, CSV y documentos de PSI
├── data/                  ← NO se sube a GitHub (ver .gitignore)
│   ├── raw/               ← lo descargado de PSI, tal cual
│   ├── processed/         ← CSV limpios en formato común
│   └── reportes/          ← reportes de validación y de descarga
├── notebooks/             ← exploración de datos (Jupyter)
├── backend/               ← API (FastAPI) + IA (RAG, function calling)
└── frontend/              ← dashboard + simuladores
```

## Primeros pasos

1. Leer [`docs/reto.md`](docs/reto.md) y [`docs/plan.md`](docs/plan.md).
2. Descargar y limpiar los datos: ver [`scripts/README.md`](scripts/README.md).
   Los datos limpios ya vienen en `data/processed/pruebas.csv`
   (formato en [`docs/formato-datos.md`](docs/formato-datos.md)).
3. Base de datos y chat con RAG: ver [`docs/base-de-datos.md`](docs/base-de-datos.md).

## Datos

Datos de NASA Physical Sciences Informatics (PSI), licencia CC0-1.0.
PSI pide citar cada experimento con su DOI (ver `docs/fuentes.md`).
