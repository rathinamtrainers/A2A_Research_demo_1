#!/usr/bin/env bash
# stop_all.sh — Stop all background A2A demo servers.
#
# Usage:
#   ./scripts/stop_all.sh

set -euo pipefail

PID_FILE="/tmp/a2a-demo.pids"

if [[ ! -f "${PID_FILE}" ]]; then
    echo "No PID file found at ${PID_FILE}. Servers may not be running."
    exit 0
fi

echo "=== A2A Demo: Stopping all servers ==="

# Kill recorded PIDs and their child processes
while read -r pid; do
    if kill -0 "${pid}" 2>/dev/null; then
        kill -- -"${pid}" 2>/dev/null || kill "${pid}" 2>/dev/null
        echo "  ✓ Stopped PID ${pid}"
    else
        echo "  - PID ${pid} not running (already stopped)"
    fi
done < "${PID_FILE}"

rm -f "${PID_FILE}"

# Fallback: kill any remaining processes on our ports
PORTS=(8001 8002 8003 8004 8005 9000)
for port in "${PORTS[@]}"; do
    pids=$(lsof -t -i:"${port}" 2>/dev/null || true)
    if [[ -n "${pids}" ]]; then
        echo "  ✓ Cleaned up leftover process on :${port}"
        echo "${pids}" | xargs kill 2>/dev/null || true
    fi
done

echo "=== All servers stopped ==="
