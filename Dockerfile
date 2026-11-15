# Imagen para desplegar el tablero (API + página) en Google Cloud Run.
# Cloud Run la construye desde GitHub en cada push a main; las claves NO van aquí:
# se ponen como variables en la consola de Cloud Run (DATABASE_URL, GROQ_API_KEY, MODELO_CHAT...).
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/app/.modelos

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# El modelo de búsqueda (MiniLM, ~220 MB) se descarga al construir la imagen, no en cada arranque.
# Debe ser el mismo con el que se vectorizaron los fragmentos (MODELO_EMBEDDINGS vacío = este).
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

# Sólo lo que usa el servidor (data/ y notebooks/ no hacen falta: los datos están en Supabase)
COPY backend backend
COPY scripts scripts
COPY frontend frontend

# Cloud Run dice en $PORT en qué puerto escuchar (8080 por defecto)
EXPOSE 8080
CMD ["sh", "-c", "python backend/app.py --host 0.0.0.0 --puerto ${PORT:-8080}"]
