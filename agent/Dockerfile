FROM python:3.11-slim

WORKDIR /app

# Copy agent code & requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent_stage3_client.py .

# Environment variable for backend URL
ENV BACKEND_URL=http://monitoring-backend:8000/ingest
ENV INTERVAL=4

CMD ["python", "agent_stage3_client.py"]
