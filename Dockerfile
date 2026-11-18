# IP-SAKTI API — deployment image for Render (or any Docker host)

FROM python:3.10-slim

WORKDIR /app

# Install dependencies first (layer caching — only reinstalls if this file changes).
# Uses a MINIMAL requirements file (just what the API imports), not the full dev
# environment freeze — pandas/beautifulsoup4/etc. from ingestion aren't needed here.
COPY requirements-api.txt .
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 -r requirements-api.txt

# Bake the v2 embedding model into the image so cold starts don't download it.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"
ENV HF_HUB_OFFLINE=1

# Copy only what the API needs to run — not the full repo (data, scripts, etc.)
# The API reads vectors from Qdrant Cloud: set QDRANT_URL / QDRANT_API_KEY on the host.
COPY lexicon/ ./lexicon/
COPY api/ ./api/

EXPOSE 8000

# Render injects $PORT at runtime — must bind to it, not a hardcoded port.
# JSON/exec form with explicit shell invocation: keeps $PORT expansion working
# while still getting proper signal handling (fixes Docker's lint warning).
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
