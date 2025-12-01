# Transcript Pipeline Dockerfile
# 
# This Dockerfile is optimized for Railway deployment (ElevenLabs cloud transcription).
# For local development with Whisper, use: docker build --build-arg INSTALL_WHISPER=true
#
FROM python:3.11-slim

# Build argument to optionally install Whisper dependencies
ARG INSTALL_WHISPER=false

# Install system dependencies
# Note: ffmpeg is needed for both ElevenLabs and Whisper
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    pkg-config \
    libopenblas-dev \
    libffi-dev \
    libssl-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
COPY requirements-local.txt .

# Install base Python dependencies (always)
RUN pip install --no-cache-dir -r requirements.txt

# Conditionally install Whisper dependencies for local use
# This adds ~2GB to the image but enables local transcription
RUN if [ "$INSTALL_WHISPER" = "true" ]; then \
        echo "Installing Whisper dependencies..." && \
        pip install --no-cache-dir openai-whisper>=20231117; \
    else \
        echo "Skipping Whisper installation (cloud mode)"; \
    fi

# Copy source code
COPY src/ ./src/
COPY server.py .
COPY frontend/ ./frontend/

# Create output directory and model cache directory
RUN mkdir -p /app/output /app/models

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
# Default model cache location for Whisper (if installed)
ENV WHISPER_MODEL_DIR=/app/models

EXPOSE 8000

# Default: API server mode
# Use --profile cli with docker-compose for CLI mode
CMD ["sh", "-c", "python -m uvicorn server:app --host 0.0.0.0 --port $PORT"]
