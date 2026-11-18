# IP-SAKTI — API + frontend in one image.
# Runs on Render's free tier (512 MB; $PORT honoured), Hugging Face Spaces
# (port 7860) or any Docker host. Vectors live in Qdrant Cloud: set
# QDRANT_URL and QDRANT_API_KEY as secrets on the host.

FROM python:3.10-slim

WORKDIR /app

# Install dependencies first (layer caching — only reinstalls if this file changes).
# MINIMAL requirements: queries are embedded with ONNX (fastembed), not PyTorch,
# which keeps the image small and the process well under 512 MB of RAM.
COPY requirements-api.txt .
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 -r requirements-api.txt

# Bake the v2 embedding model into the image so cold starts don't download it.
# The cache lives under /app so a non-root runtime user can read it.
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/app/.cache/fastembed')" \
    && chmod -R a+rX /app/.cache
ENV HF_HUB_OFFLINE=1

# Copy only what the app needs to run — not the full repo (data, scripts, etc.)
COPY lexicon/ ./lexicon/
COPY api/ ./api/
COPY frontend/index.html ./frontend/index.html

# Run as an unprivileged user (uid 1000 also matches Hugging Face Spaces).
RUN useradd -m -u 1000 user
USER 1000

EXPOSE 7860

# Render injects $PORT; Spaces route to 7860. Shell form keeps $PORT
# expansion while exec-ing uvicorn for proper signal handling.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
