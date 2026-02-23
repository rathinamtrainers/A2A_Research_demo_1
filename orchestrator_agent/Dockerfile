# Dockerfile for orchestrator_agent
# Deployed to Vertex AI Agent Engine via 'adk deploy agent_engine'
# This Dockerfile is provided as a reference; Agent Engine typically
# handles containerisation automatically via the ADK deploy command.

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install OS-level dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer cache optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY shared/ ./shared/
COPY orchestrator_agent/ ./orchestrator_agent/

# Expose the ADK web UI / API server port
EXPOSE 8000

# Default: run ADK API server exposing the orchestrator as an A2A endpoint
CMD ["adk", "api_server", "--a2a", "--port", "8000", "./orchestrator_agent/"]
