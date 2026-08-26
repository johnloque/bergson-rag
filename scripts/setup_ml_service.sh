#!/usr/bin/env bash
set -euo pipefail

# Sets up the native ml_service (docs/dockerization.md, feat/native-ml-service)
# -- the fast, default path for dense embedding, sparse embedding, and
# cross-encoder reranking (src/ml_service/main.py). Docker Desktop on Apple
# Silicon has no Metal passthrough, so a containerized sentence-transformers
# process silently falls back to CPU -- measured ~31x slower for the
# cross-encoder reranker alone (docs/dockerization.md). This script is NOT
# Docker-based -- it runs `uvicorn` directly on the host, same convention as
# scripts/setup_ollama.sh (fix/ollama-native-default) for the analogous
# Ollama case. No corresponding service block exists in docker-compose.yml.
#
# Usage: ./scripts/setup_ml_service.sh
# Env overrides: ML_SERVICE_PORT (default 8100), ML_SERVICE_HOST (default
# http://localhost:<port>, used for the readiness poll and the endpoint
# verification below).

PORT="${ML_SERVICE_PORT:-8100}"
HOST_URL="${ML_SERVICE_HOST:-http://localhost:${PORT}}"

probe() {
  # A cheap readiness probe: an empty-texts request exercises the same
  # startup/routing path as a real one (SentenceTransformer.encode([]) is
  # valid) without paying for actual inference.
  curl -fsS -o /dev/null -X POST "${HOST_URL}/embed/dense" \
    -H 'Content-Type: application/json' -d '{"texts": []}'
}

wait_for_server() {
  echo "Waiting for ml_service at ${HOST_URL} (first run loads BGE-M3 + the" \
       "cross-encoder reranker -- several GB -- this can take a while)..."
  for _ in $(seq 1 150); do
    if probe 2>/dev/null; then
      echo "OK: ml_service is responding."
      return 0
    fi
    sleep 2
  done
  echo "FAIL: ml_service never responded at ${HOST_URL}. Check /tmp/ml_service.log." >&2
  exit 1
}

echo "Syncing dependencies (uv sync)..."
uv sync

if probe 2>/dev/null; then
  echo "ml_service already running at ${HOST_URL}."
else
  echo "Starting ml_service in the background (uvicorn, port ${PORT})..."
  nohup uv run uvicorn src.ml_service.main:app --host 0.0.0.0 --port "${PORT}" \
    >/tmp/ml_service.log 2>&1 &
  disown
  wait_for_server
fi

echo ""
echo "Verifying all three endpoints with real requests, not just a successful process start..."

echo "-> POST /embed/dense"
dense_response="$(curl -fsS -X POST "${HOST_URL}/embed/dense" \
  -H 'Content-Type: application/json' \
  -d '{"texts": ["La duree est le fondement de la vie interieure."]}')"
if ! grep -q '"vectors"' <<< "${dense_response}"; then
  echo "FAIL: /embed/dense response missing 'vectors': ${dense_response}" >&2
  exit 1
fi
echo "OK: /embed/dense returned a dense vector."

echo "-> POST /embed/sparse"
sparse_response="$(curl -fsS -X POST "${HOST_URL}/embed/sparse" \
  -H 'Content-Type: application/json' \
  -d '{"texts": ["La duree est le fondement de la vie interieure."]}')"
if ! grep -q '"indices"' <<< "${sparse_response}" || ! grep -q '"values"' <<< "${sparse_response}"; then
  echo "FAIL: /embed/sparse response missing 'indices'/'values': ${sparse_response}" >&2
  exit 1
fi
echo "OK: /embed/sparse returned indices/values."

echo "-> POST /rerank"
rerank_response="$(curl -fsS -X POST "${HOST_URL}/rerank" \
  -H 'Content-Type: application/json' \
  -d '{"query": "Que signifie la duree chez Bergson ?", "texts": ["La duree est le fondement de la vie interieure.", "Le chemin de fer relie les grandes villes de province."]}')"
if ! grep -q '"scores"' <<< "${rerank_response}"; then
  echo "FAIL: /rerank response missing 'scores': ${rerank_response}" >&2
  exit 1
fi
echo "OK: /rerank returned scores."

echo ""
echo "Native ml_service ready at ${HOST_URL} -- dense/sparse embedding and reranking all verified."
