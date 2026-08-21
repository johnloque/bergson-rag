#!/usr/bin/env bash
set -euo pipefail

# Regression test for the VITE_API_BASE build-ARG mistake (docs/ROADMAP.md,
# Sprint 9): asserts the frontend's *served* JS bundle references a
# host-reachable API URL (localhost:<port>), never the internal Docker
# service name (api:8000). Getting this backwards builds and runs fine,
# and can even pass a container-only smoke test -- it only fails once a
# real browser tries to call the internal name, which never resolves
# outside the Docker network. See frontend/Dockerfile and
# docker-compose.yml's `frontend.build.args`.
#
# Usage: ./scripts/test_frontend_arg.sh
# Requires: `docker compose up -d frontend` (or `make run` /
# `make quickstart`) already complete.

FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
INTERNAL_SERVICE_NAME="${INTERNAL_SERVICE_NAME:-api:8000}"
HOST_API_URL="${HOST_API_URL:-localhost:8000}"

index_html="$(curl -fsS "${FRONTEND_URL}/")"

# Vite emits one or more hashed JS entrypoints referenced from index.html.
js_paths="$(grep -oE '/assets/[A-Za-z0-9_.-]+\.js' <<< "${index_html}" | sort -u)"
if [ -z "${js_paths}" ]; then
  echo "FAIL: no JS asset referenced from ${FRONTEND_URL}/ -- build likely broken" >&2
  exit 1
fi

found_host_url=0
while IFS= read -r js_path; do
  bundle="$(curl -fsS "${FRONTEND_URL}${js_path}")"
  if grep -qF "${INTERNAL_SERVICE_NAME}" <<< "${bundle}"; then
    echo "FAIL: ${js_path} references the internal Docker service name (${INTERNAL_SERVICE_NAME})," >&2
    echo "      which only resolves container-to-container, never from a real browser." >&2
    exit 1
  fi
  if grep -qF "${HOST_API_URL}" <<< "${bundle}"; then
    found_host_url=1
  fi
done <<< "${js_paths}"

if [ "${found_host_url}" -ne 1 ]; then
  echo "FAIL: no JS asset references the host-reachable API URL (${HOST_API_URL})." >&2
  echo "      Check VITE_API_BASE was set correctly at build time" >&2
  echo "      (frontend/Dockerfile, docker-compose.yml's frontend.build.args)." >&2
  exit 1
fi

echo "OK: served frontend bundle references ${HOST_API_URL}, not ${INTERNAL_SERVICE_NAME}"
