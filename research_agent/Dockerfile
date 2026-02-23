# Dockerfile for research_agent
# Deploy: gcloud run deploy research-agent --source . --region us-central1

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY research_agent/ ./research_agent/

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn research_agent.agent:app --host 0.0.0.0 --port ${PORT}"]
