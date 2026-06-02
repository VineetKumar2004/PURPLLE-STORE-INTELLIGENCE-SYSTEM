#!/bin/bash
set -e

echo "[entrypoint] Running pipeline..."
python scripts/run_pipeline.py

echo "[entrypoint] Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
