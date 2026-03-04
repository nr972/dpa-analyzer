#!/usr/bin/env bash
set -e

mkdir -p data/uploads data/reports data/matrices

# Start API in background
uvicorn dpa_app.main:app --host 0.0.0.0 --port "${API_PORT:-8000}" &

# Wait for API
for i in $(seq 1 30); do
    if curl -s "http://127.0.0.1:${API_PORT:-8000}/health" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Start Streamlit in foreground
streamlit run dpa_frontend/app.py \
    --server.port "${PORT:-8501}" \
    --server.address 0.0.0.0 \
    --server.headless true
