# scripts/

Shell scripts for local development, testing, and deployment.

## Files

| Script | Description |
|---|---|
| `start_all.sh` | Start all local A2A agent servers in background processes |
| `stop_all.sh` | Stop all background servers started by `start_all.sh` |
| `deploy_cloud_run.sh` | Deploy agent servers to Google Cloud Run |
| `deploy_agent_engine.sh` | Deploy orchestrator to Vertex AI Agent Engine |
| `generate_protos.sh` | Generate Python gRPC stubs from `protos/a2a_demo.proto` |

## Quick Start

```bash
# Make scripts executable (first time only):
chmod +x scripts/*.sh

# Start all local servers:
./scripts/start_all.sh

# Stop all local servers:
./scripts/stop_all.sh

# Generate gRPC stubs:
./scripts/generate_protos.sh

# Deploy to Cloud Run (all agents):
./scripts/deploy_cloud_run.sh

# Deploy orchestrator to Agent Engine:
./scripts/deploy_agent_engine.sh
```

## Local Server Ports

| Agent | Port | URL |
|---|---|---|
| weather_agent | 8001 | http://localhost:8001 |
| research_agent | 8002 | http://localhost:8002 |
| code_agent | 8003 | http://localhost:8003 |
| data_agent | 8004 | http://localhost:8004 |
| async_agent | 8005 | http://localhost:8005 |
| webhook_server | 9000 | http://localhost:9000 |
