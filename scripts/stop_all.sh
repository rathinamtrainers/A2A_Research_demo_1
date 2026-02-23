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

while read -r pid; do
    if kill -0 "${pid}" 2>/dev/null; then
        kill "${pid}" && echo "  ✓ Stopped PID ${pid}"
    else
        echo "  - PID ${pid} not running (already stopped)"
    fi
done < "${PID_FILE}"

rm -f "${PID_FILE}"
echo "=== All servers stopped ==="
