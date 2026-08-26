#!/usr/bin/env bash
set -euo pipefail

# Sets up native (host) Ollama -- the fast, default path on Apple Silicon
# (docs/dockerization.md): Docker Desktop cannot pass the Mac's GPU
# (Metal) through to a container, so containerized Ollama runs CPU-only,
# measured 3-5x slower than running it natively. This script is NOT
# Docker-based -- it installs and runs Ollama directly on the host.
#
# Usage: ./scripts/setup_ollama.sh
# Env overrides: OLLAMA_MODEL (default mistral), OLLAMA_HOST (default
# http://localhost:11434, used only for the readiness poll and the final
# verification request below).

MODEL="${OLLAMA_MODEL:-mistral}"
HOST_URL="${OLLAMA_HOST:-http://localhost:11434}"

wait_for_server() {
  echo "Waiting for Ollama server at ${HOST_URL}..."
  for _ in $(seq 1 30); do
    if curl -fsS "${HOST_URL}/api/version" >/dev/null 2>&1; then
      echo "OK: Ollama server is responding."
      return 0
    fi
    sleep 1
  done
  echo "FAIL: Ollama server never responded at ${HOST_URL}" >&2
  exit 1
}

start_ollama_background() {
  echo "Starting 'ollama serve' in the background..."
  nohup ollama serve >/tmp/ollama_serve.log 2>&1 &
  disown
}

case "$(uname -s)" in
  Darwin)
    if ! command -v ollama >/dev/null 2>&1; then
      if ! command -v brew >/dev/null 2>&1; then
        echo "FAIL: Homebrew not found. Install it from https://brew.sh, then re-run this script." >&2
        exit 1
      fi
      echo "Installing Ollama via Homebrew..."
      brew install ollama
    else
      echo "Ollama already installed ($(command -v ollama))."
    fi

    if ! curl -fsS "${HOST_URL}/api/version" >/dev/null 2>&1; then
      # brew services runs Ollama as a launchd service that survives
      # reboots; fall back to a plain backgrounded `ollama serve` if
      # brew services isn't set up (e.g. Ollama installed some other way).
      if ! brew services start ollama >/dev/null 2>&1; then
        start_ollama_background
      fi
    else
      echo "Ollama server already running."
    fi
    ;;

  Linux)
    if ! command -v ollama >/dev/null 2>&1; then
      echo "Installing Ollama via the official install script..."
      curl -fsSL https://ollama.com/install.sh | sh
    else
      echo "Ollama already installed ($(command -v ollama))."
    fi

    if ! curl -fsS "${HOST_URL}/api/version" >/dev/null 2>&1; then
      # The official installer sets up and starts a systemd service on
      # most distros; fall back to a plain backgrounded `ollama serve` if
      # systemd isn't available/managing it (e.g. inside a container).
      if ! { command -v systemctl >/dev/null 2>&1 && systemctl start ollama >/dev/null 2>&1; }; then
        start_ollama_background
      fi
    else
      echo "Ollama server already running."
    fi
    ;;

  *)
    echo "FAIL: unsupported platform $(uname -s). This script supports macOS and Linux only." >&2
    exit 1
    ;;
esac

wait_for_server

echo "Pulling model '${MODEL}'..."
ollama pull "${MODEL}"

# Verify with a real request/response, not just a successful pull exit
# code -- a pulled-but-unloadable model, or a server that accepts
# connections but can't actually serve, wouldn't be caught otherwise.
echo "Verifying '${MODEL}' with a real generation request..."
response="$(ollama run "${MODEL}" "Reply with the single word: OK" 2>&1)"
if [ -z "$(echo "${response}" | tr -d '[:space:]')" ]; then
  echo "FAIL: got an empty response from '${MODEL}'. Output was:" >&2
  echo "${response}" >&2
  exit 1
fi

echo "OK: '${MODEL}' responded:"
echo "${response}"
echo ""
echo "Native Ollama ready at ${HOST_URL}, model '${MODEL}' pulled and verified."
