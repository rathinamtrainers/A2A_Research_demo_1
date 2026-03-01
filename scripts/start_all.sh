#!/usr/bin/env bash
# start_all.sh — Start all local A2A agent servers and the webhook receiver.
#
# Usage:
#   ./scripts/start_all.sh
#
# Prerequisites:
#   - Virtual environment activated: source .venv/bin/activate
#   - .env file populated with required variables
#   - tmux installed (optional, for split-pane view): brew install tmux
#
# Each agent runs in a background process. PID file at /tmp/a2a-demo.pids

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load environment
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

PID_FILE="/tmp/a2a-demo.pids"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOG_DIR}"

echo "=== A2A Demo: Starting all servers ==="

# Function to start a background server and record its PID
start_server() {
    local name="$1"
    local cmd="$2"
    local log="${LOG_DIR}/${name}.log"

    echo "  Starting ${name}..."
    eval "${cmd}" > "${log}" 2>&1 &
    local pid=$!
    echo "${pid}" >> "${PID_FILE}"
    echo "  ✓ ${name} (PID ${pid}) → ${log}"
}

# Clear old PID file
> "${PID_FILE}"

# Change to project root
cd "${PROJECT_ROOT}"

# Start all A2A agent servers (using uvicorn with each agent's to_a2a() app)
start_server "weather_agent" \
    ".venv/bin/uvicorn weather_agent.agent:app --host 0.0.0.0 --port 8001"

start_server "research_agent" \
    ".venv/bin/uvicorn research_agent.agent:app --host 0.0.0.0 --port 8002"

start_server "code_agent" \
    ".venv/bin/uvicorn code_agent.agent:app --host 0.0.0.0 --port 8003"

start_server "data_agent" \
    ".venv/bin/uvicorn data_agent.agent:app --host 0.0.0.0 --port 8004"

start_server "async_agent" \
    ".venv/bin/uvicorn async_agent.agent:app --host 0.0.0.0 --port 8005"

# Start webhook receiver
start_server "webhook_server" \
    ".venv/bin/uvicorn webhook_server.main:app --host 0.0.0.0 --port 9000"

echo ""
echo "=== All servers started ==="
echo "  weather_agent  → http://localhost:8001"
echo "  research_agent → http://localhost:8002"
echo "  code_agent     → http://localhost:8003"
echo "  data_agent     → http://localhost:8004"
echo "  async_agent    → http://localhost:8005"
echo "  webhook_server → http://localhost:9000"
echo ""
echo "Logs: ${LOG_DIR}/"
echo "PIDs: ${PID_FILE}"
echo ""
echo "To stop all: ./scripts/stop_all.sh"
