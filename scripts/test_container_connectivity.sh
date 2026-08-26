#!/usr/bin/env bash
set -euo pipefail

# Container-to-container connectivity check (docs/ROADMAP.md, Sprint 9):
# confirms the api container reaches qdrant and ollama by their internal
# Docker service names. This is the counterpart to test_frontend_arg.sh,
# which checks the opposite direction -- the browser must NEVER use those
# internal names.
#
# Usage: ./scripts/test_container_connectivity.sh
# Requires: `docker compose up` (or `make run` / `make quickstart`)
# already complete.

echo "api -> qdrant (http://qdrant:6333/healthz):"
docker compose exec -T api curl -fsS http://qdrant:6333/healthz
echo " OK"

echo "api -> ollama (http://ollama:11434/):"
docker compose exec -T api curl -fsS http://ollama:11434/
echo " OK"

echo ""
echo "OK: api reaches both qdrant and ollama by internal service name."
