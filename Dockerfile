# IP-SAKTI — API + frontend in one image.
# Runs on Hugging Face Spaces (Docker SDK, port 7860) or any Docker host
# such as Render ($PORT is honoured). Vectors live in Qdrant Cloud: set
# QDRANT_URL and QDRANT_API_KEY as secrets on the host.

FROM python:3.10-slim

WORKDIR /app

# CPU-only PyTorch first: the default Linux wheel bundles CUDA (~2 GB) that
# a CPU host never uses. sentence-transformers then reuses this install.
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 \
        torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies first (layer caching — only reinstalls if this file changes).
# Uses a MINIMAL requirements file (just what the API imports), not the full dev
# environment freeze — pandas/beautifulsoup4/etc. from ingestion aren't needed here.
COPY requirements-api.txt .
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 -r requirements-api.txt

# Bake the v2 embedding model into the image so cold starts don't download it.
# HF_HOME is outside /root so the non-root user Spaces runs as (uid 1000) can read it.
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')" \
    && chmod -R a+rX /app/.cache
ENV HF_HUB_OFFLINE=1

# Copy only what the app needs to run — not the full repo (data, scripts, etc.)
COPY lexicon/ ./lexicon/
COPY api/ ./api/
COPY frontend/index.html ./frontend/index.html

# Spaces run the container as uid 1000; make sure it can read everything.
RUN useradd -m -u 1000 user 2>/dev/null || true
USER 1000

EXPOSE 7860

# Spaces route to app_port (7860); Render injects $PORT. Shell form keeps
# $PORT expansion while exec-ing uvicorn for proper signal handling.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
