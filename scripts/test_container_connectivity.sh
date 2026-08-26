#!/usr/bin/env bash
set -euo pipefail

# Container-to-container connectivity check (docs/dockerization.md):
# confirms the api container reaches qdrant by its internal Docker
# service name, and reaches Ollama at whatever OLLAMA_API_BASE actually
# resolves to for the active mode -- this is the counterpart to
# test_frontend_arg.sh, which checks the opposite direction (the browser
# must NEVER use internal service names).
#
# Two Ollama modes, auto-detected from whether the `ollama` service
# container is running (docs/dockerization.md):
#   - native (default, `make run`): the `ollama` service isn't started at
#     all -- api reaches native host Ollama via
#     host.docker.internal:11434.
#   - containerized (opt-in, `make run-with-ollama`): api reaches the
#     `ollama` service by its internal Docker name, ollama:11434.
#
# Usage: ./scripts/test_container_connectivity.sh
# Requires: `docker compose up` / `make run` (native) or
# `docker compose --profile with-ollama up` / `make run-with-ollama`
# (containerized) already complete.

echo "api -> qdrant (http://qdrant:6333/healthz):"
docker compose exec -T api curl -fsS http://qdrant:6333/healthz
echo " OK"

if [ -n "$(docker compose ps --status running -q ollama 2>/dev/null)" ]; then
  echo "Detected containerized Ollama (with-ollama profile active)."
  echo "api -> ollama (http://ollama:11434/):"
  docker compose exec -T api curl -fsS http://ollama:11434/
  echo " OK"
  echo ""
  echo "OK: api reaches both qdrant and ollama by internal service name."
else
  echo "Detected native Ollama (no with-ollama profile / default mode)."
  echo "api -> host Ollama (http://host.docker.internal:11434/):"
  docker compose exec -T api curl -fsS http://host.docker.internal:11434/
  echo " OK"
  echo ""
  echo "OK: api reaches qdrant by internal service name and reaches"
  echo "native host Ollama via host.docker.internal."
fi
