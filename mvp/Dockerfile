# YouTube Shorts Factory Dockerfile

# Base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV PIP_DEFAULT_TIMEOUT=100
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data/assets/music \
    /app/data/assets/fonts \
    /app/data/outputs \
    /app/data/temp \
    /app/logs

# Set permissions
RUN chown -R nobody:nogroup /app && \
    chmod -R 755 /app

# Expose ports
EXPOSE 8501  # Streamlit
EXPOSE 8000  # FastAPI (if used)

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default command (can be overridden)
CMD ["python", "scripts/run_worker.py"]
