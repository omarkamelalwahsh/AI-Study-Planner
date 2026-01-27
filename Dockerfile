# Enterprise RAG Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Requirements
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy Code
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1
ENV PORT=8001

# Start
CMD ["./scripts/startup.sh"]
