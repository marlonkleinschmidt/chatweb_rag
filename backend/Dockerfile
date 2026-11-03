# Runtime image for the FastAPI backend (PRD §10, task 6.4).
# Base: slim Python 3.12 to match the version pinned by the project (AGENTS.md).
FROM python:3.12-slim

# Avoid .pyc files (image stays lean) and unbuffered stdout so logs show up
# immediately in `docker compose logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so Docker can cache this layer while the
# application code changes. requirements.txt pins direct dependencies with ==
# (transitives such as chromadb/openai are resolved by pip at build time).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (tests, .env and data/ are excluded by .dockerignore;
# secrets are injected at runtime via compose `env_file`, never baked in).
COPY app ./app

# Run as a non-root user. /app/data is the mount point for the persistence
# volume: config.py resolves data/documents, data/chroma and data/app.db
# relative to WORKDIR, and db.py creates the subdirectories on startup.
RUN useradd --create-home appuser \
    && mkdir /app/data \
    && chown appuser:appuser /app/data
USER appuser

EXPOSE 8000

# 0.0.0.0 is required *inside* the container so the published port works;
# exposure stays loopback-only because docker-compose.yml maps the host port
# as 127.0.0.1:8000:8000 (the PRD rule applies to the host, not the container).
# Exec form (JSON) sends signals straight to uvicorn; Dockerfile JSON syntax
# requires double quotes, which overrides the project single-quote rule here.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
