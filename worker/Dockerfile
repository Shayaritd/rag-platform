FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU version separately to keep image small
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy api requirements and install
COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/app ./app
COPY worker/tasks ./worker/tasks

ENV PYTHONPATH=/app

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info"]
