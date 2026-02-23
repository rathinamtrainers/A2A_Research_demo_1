# protos/

Protocol Buffer definitions for the A2A gRPC transport binding.

Reference: F21 — gRPC Transport (A2A v0.3).

## Files

| File | Description |
|---|---|
| `a2a_demo.proto` | gRPC service definition mirroring the A2A JSON-RPC API |

## Generating Python Stubs

Run from the project root with the venv activated:

```bash
source .venv/bin/activate

python -m grpc_tools.protoc \
  -I protos/ \
  --python_out=protos/ \
  --grpc_python_out=protos/ \
  protos/a2a_demo.proto
```

This generates:
- `protos/a2a_demo_pb2.py` — Protobuf message classes
- `protos/a2a_demo_pb2_grpc.py` — gRPC service stubs

## Usage After Code Generation

```python
from protos import a2a_demo_pb2, a2a_demo_pb2_grpc
from a2a_client.grpc_client import A2AGrpcClient

async def main():
    client = A2AGrpcClient(host="localhost", port=50051)
    await client.connect()
    result = await client.send_message("Hello via gRPC!")
    print(result)
```

## Official A2A Proto

The official A2A protocol proto definitions are maintained at:
https://github.com/a2aproject/A2A

For production use, prefer the official definitions over this demo file.
