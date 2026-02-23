# Dockerfile for weather_agent
# Deployed to Cloud Run via:
#   gcloud run deploy weather-agent --source . --region us-central1 --allow-unauthenticated

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities and this agent's code
COPY shared/ ./shared/
COPY weather_agent/ ./weather_agent/

# Cloud Run provides PORT env var; default to 8080
ENV PORT=8080

EXPOSE 8080

# Run the ADK A2A server for the weather agent
CMD ["sh", "-c", "uvicorn weather_agent.agent:app --host 0.0.0.0 --port ${PORT}"]
