# Transcript Pipeline Dockerfile
FROM python:3.11-slim

# Install system dependencies
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

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create directories for output and models
RUN mkdir -p /app/output /app/models

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV WHISPER_CACHE_DIR=/app/models

# Create entry point script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Check if Whisper model cache is empty and download base model\n\
if [ -z "$(ls -A /app/models)" ]; then\n\
    echo "Downloading Whisper base model to cache..."\n\
    python -c "import whisper; whisper.load_model(\"base\", download_root=\"/app/models\")"\n\
    echo "Model cached successfully"\n\
fi\n\
\n\
# Run the main application\n\
exec python -m src.main "$@"\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
