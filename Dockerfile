# Multi-stage Dockerfile for MV Face Recognition System
# Optimized for Zeabur deployment with minimal image size

FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends -o Acquire::Retries=3 \
    build-essential \
    cmake \
    pkg-config \
    libgl1-mesa-dev \
    libglib2.0-dev \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgcc-s1 \
    ffmpeg \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies to a temporary location
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends -o Acquire::Retries=3 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgcc-s1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get clean

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Set working directory
WORKDIR /app

# Create app user for security
RUN useradd --create-home --shell /bin/bash app

# Copy application code
COPY --chown=app:app . .

# Create necessary directories
RUN mkdir -p cache output source/videos source/photo/contestants fonts \
    && chown -R app:app /app

# Switch to app user
USER app

# Set Python path
ENV PYTHONPATH=/app

# Environment variables for production
ENV GRADIO_SERVER_NAME=0.0.0.0
ENV GRADIO_SERVER_PORT=8080
ENV GRADIO_SHARE=False
ENV GRADIO_DEBUG=False
ENV NO_ALBUMENTATIONS_UPDATE=1
ENV INSIGHTFACE_DISABLE_LOGGING=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose ports
EXPOSE 8080 8081
# Port 8080: Health check endpoint
# Port 8081: Main Gradio interface

# Start command
CMD ["python", "app.py"]