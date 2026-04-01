FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for ML, audio, and web scraping
RUN apt-get update && apt-get install -y \
    gcc g++ ffmpeg libsndfile1 libasound2-dev portaudio19-dev \
    build-essential pkg-config libffi-dev libssl-dev \
    libxml2-dev libxslt1-dev libjpeg-dev libpng-dev zlib1g-dev \
    curl wget git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY MM2/requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy MM2 source files into /app/MM2
COPY MM2 /app/MM2

# Copy .env from project root if present
COPY .env /app/.env

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "MM2.main:app", "--bind", "0.0.0.0:8080", "--workers=1", "--threads=2", "--timeout=0"]