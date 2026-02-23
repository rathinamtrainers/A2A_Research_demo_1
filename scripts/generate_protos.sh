#!/usr/bin/env bash
# generate_protos.sh — Generate Python gRPC stubs from proto definitions.
#
# Reference: F21 — gRPC Transport.
#
# Usage:
#   ./scripts/generate_protos.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Generating gRPC Python stubs ==="

cd "${PROJECT_ROOT}"

.venv/bin/python -m grpc_tools.protoc \
    -I protos/ \
    --python_out=protos/ \
    --grpc_python_out=protos/ \
    protos/a2a_demo.proto

echo "  ✓ Generated: protos/a2a_demo_pb2.py"
echo "  ✓ Generated: protos/a2a_demo_pb2_grpc.py"
echo ""
echo "Import in Python:"
echo "  from protos import a2a_demo_pb2, a2a_demo_pb2_grpc"
