# Multi-stage Dockerfile for MV Face Recognition System
# Optimized for Zeabur deployment with minimal image size

FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgcc-s1 \
    ffmpeg \
    libopencv-dev \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgcc-s1 \
    ffmpeg \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Create app user for security
RUN useradd --create-home --shell /bin/bash app

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/app/.local

# Copy application code
COPY --chown=app:app . .

# Create necessary directories
RUN mkdir -p cache output source/videos source/photo/contestants fonts \
    && chown -R app:app /app

# Switch to app user
USER app

# Set Python path
ENV PATH=/home/app/.local/bin:$PATH
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

# Expose port
EXPOSE 8080

# Start command
CMD ["python", "app.py"]