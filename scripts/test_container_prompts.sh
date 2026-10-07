#!/usr/bin/env bash
set -euo pipefail

# Container half of the prompts/ packaging check (docs/prompts.md): builds
# the api image and confirms src/prompts/loader.py finds prompts/ inside it,
# with the same hashes as on the host. The static half (Dockerfile copies
# prompts/, .dockerignore doesn't drop it) runs in the fast suite:
# tests/test_prompt_loader.py::test_api_image_ships_prompts_dir.
#
# Not part of CI: building the api image (torch, spaCy, ...) takes minutes.
# Run it after touching the Dockerfile, .dockerignore or src/prompts/.
#
# Usage: ./scripts/test_container_prompts.sh   (or: make test-container-prompts)

MANIFEST_CMD='import json; from src.prompts.loader import PROMPTS_DIR, get_prompt_manifest; print(PROMPTS_DIR); print(json.dumps(get_prompt_manifest(), sort_keys=True))'

docker compose build api

echo "prompts/ as resolved inside the api image:"
container_output="$(docker compose run --rm --no-deps -T api python -c "$MANIFEST_CMD")"
echo "$container_output" | head -1

host_manifest="$(uv run python -c "$MANIFEST_CMD" | tail -1)"
container_manifest="$(echo "$container_output" | tail -1)"

if [ "$host_manifest" != "$container_manifest" ]; then
  echo "FAIL: prompt manifest differs between host and container" >&2
  echo "host:      $host_manifest" >&2
  echo "container: $container_manifest" >&2
  exit 1
fi
echo "OK: the api image loads every prompt, with the host's hashes."
