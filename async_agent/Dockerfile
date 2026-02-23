# Dockerfile for async_agent
# Deploy: gcloud run deploy async-agent --source . --region us-central1

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY async_agent/ ./async_agent/

ENV PORT=8080
EXPOSE 8080

# Run uvicorn directly (not via adk api_server) since this agent manages
# its own A2A request handler for push notification support.
CMD ["sh", "-c", "uvicorn async_agent.agent:app --host 0.0.0.0 --port ${PORT}"]
