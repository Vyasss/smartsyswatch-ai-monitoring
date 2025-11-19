# Use official Python image
FROM python:3.11-slim

# Create work directory inside container
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code and ML models into the image
COPY backend ./backend

# SQLite DB will be created as /app/metrics.db inside container at runtime

# Expose backend port
EXPOSE 8000

# Start FastAPI with uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
