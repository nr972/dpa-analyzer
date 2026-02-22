#!/usr/bin/env bash
set -e

# Privacy & DPA Analyzer — One-command startup
# Starts both the FastAPI backend and Streamlit frontend.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

API_PORT=8000
FRONTEND_PORT=8501
API_PID=""

cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    if [ -n "$API_PID" ]; then
        kill "$API_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup INT TERM

# Check Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Error: Python 3 is not installed.${NC}"
    echo "Please install Python 3.11+ from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}Found Python $PYTHON_VERSION${NC}"

# Install dependencies (first run or after updates)
if [ ! -d ".venv" ] && ! pip show dpa-analyzer &>/dev/null 2>&1; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -e ".[dev]"
fi

# Create data directories
mkdir -p data/uploads data/reports data/matrices

# Start API server in background
echo -e "${GREEN}Starting API server on port $API_PORT...${NC}"
uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT" &
API_PID=$!

# Wait for API to be ready
echo "Waiting for API to start..."
for i in $(seq 1 30); do
    if curl -s "http://localhost:$API_PORT/health" >/dev/null 2>&1; then
        echo -e "${GREEN}API is ready!${NC}"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e "${RED}API failed to start within 30 seconds.${NC}"
        cleanup
    fi
    sleep 1
done

# Start Streamlit frontend (foreground)
echo -e "${GREEN}Starting frontend on port $FRONTEND_PORT...${NC}"
echo -e "${GREEN}Open http://localhost:$FRONTEND_PORT in your browser.${NC}"
echo ""
streamlit run frontend/app.py \
    --server.port "$FRONTEND_PORT" \
    --server.address 0.0.0.0 \
    --server.headless true
