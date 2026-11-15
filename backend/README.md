# Backend

API + IA del proyecto. Pendiente (Fase 2 del plan).

## Lo que ya existe

- **Base de datos** Postgres + pgvector: esquema en [`esquema.sql`](esquema.sql), explicación y
  puesta en marcha en [`docs/base-de-datos.md`](../docs/base-de-datos.md).
  Tablas: `experimentos`, `pruebas`, `fragmentos` y la vista `experimentos_resumen`.
- **Búsqueda del RAG**: `scripts/buscar.py` tiene la función `buscar()` y
  `scripts/embeddings.py` la clase `Vectorizador`; el backend puede importarlas.
- La dirección de la base va en `.env` (`DATABASE_URL`), que nunca se sube a GitHub.

## Propuesta para la Fase 2

- **FastAPI** (Python)
- Endpoints: `/experimentos`, `/experimentos/{id}`, `/pruebas` (con filtros), `/export.csv`, `/chat`
- Chat con RAG que siempre cita experimento + DOI y dice "no hay datos" cuando no los hay
- Números exactos con SQL sobre `pruebas` (no con el RAG)
- Function calling para controlar los simuladores
