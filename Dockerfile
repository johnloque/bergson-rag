# Backend API image (Sprint 9, docs/ROADMAP.md). Single-stage: this
# project's dependency set (spaCy, sentence-transformers, ragas, ...) has
# no meaningful build/runtime split, so a multi-stage build would only add
# complexity here without shrinking the image.
FROM python:3.12-slim

# curl: this image's own healthcheck below, and manual container-to-
# container debugging (docker compose exec api curl qdrant:6333/healthz).
# libgomp1: OpenMP runtime some torch/sentence-transformers CPU ops need.
# git: ragas imports GitPython at module load time (src/generation/
# faithfulness.py -> ragas.dataset_schema -> ragas.experiment), which
# raises ImportError without a git executable on PATH -- unnoticed in
# host dev since the host always has git, but fatal here without it.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:${PATH}"

# Dependency layer cached separately from source: an src/ change alone
# doesn't force re-resolving/re-downloading spaCy/torch/sentence-
# transformers. pyproject.toml/uv.lock are this project's single
# dependency source (reused as-is, no parallel requirements.txt).
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ src/
RUN uv sync --frozen --no-dev

EXPOSE 8000

HEALTHCHECK --interval=5s --timeout=5s --start-period=15s --retries=10 \
    CMD curl -f http://localhost:8000/docs || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
