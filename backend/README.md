# Backend

API + IA del proyecto. Pendiente (Fase 2 del plan).

Propuesta:
- **FastAPI** (Python)
- **Postgres + pgvector** (Supabase o Neon): tablas `experimentos`, `pruebas` y embeddings
- Endpoints: `/experimentos`, `/experimentos/{id}`, `/pruebas`, `/export.csv`, `/chat`
- Chat con RAG que siempre cita experimento + DOI
- Function calling para controlar los simuladores

Las claves van en un archivo `.env` (nunca se sube a GitHub).
