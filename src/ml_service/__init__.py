"""Standalone native ML service (feat/native-ml-service, docs/dockerization.md).

Separate from src/api/ on purpose: this process exists to run natively on
the host (never containerized by default) so `sentence-transformers` picks
up Metal/MPS automatically, the same reasoning already applied to Ollama in
fix/ollama-native-default. See src/ml_service/main.py for the app itself
and src/api/ml_client.py for the HTTP client `src/api/dependencies.py`
calls into when `ML_SERVICE_URL` is set.
"""
