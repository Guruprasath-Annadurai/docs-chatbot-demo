FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache
WORKDIR /app

# CPU-only PyTorch keeps the image much smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch
COPY requirements.txt .
RUN pip install -r requirements.txt

# Download the local embedding model at build time so the first start is quick
# and the container works offline.
ARG LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${LOCAL_EMBEDDING_MODEL}')"

COPY app ./app
COPY sample_docs ./sample_docs

RUN useradd --create-home appuser && mkdir -p /app/data && chown -R appuser /app/data
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
