# Simplified Dockerfile for Zeabur deployment
# This builds both frontend and backend in a single container

FROM python:3.11-slim as backend-builder

# Install system dependencies for backend
RUN apt-get update && apt-get install -y \
    gcc g++ cmake libglib2.0-0 libsm6 libxext6 \
    libxrender-dev libgomp1 ffmpeg wget \
    && rm -rf /var/lib/apt/lists/*

# Setup backend
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .

# Frontend builder stage
FROM node:18-alpine as frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN rm -rf node_modules package-lock.json && npm install --omit=dev
COPY frontend/ .
RUN npm run build

# Final production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgomp1 ffmpeg nginx curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend
WORKDIR /app
COPY --from=backend-builder /app/backend ./backend
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Setup nginx
COPY nginx-default.conf /etc/nginx/sites-available/default

# Create required directories
RUN mkdir -p /app/source/videos /app/source/photo/contestants /app/backend/data

# Environment variables
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
ENV PYTHONUNBUFFERED=1
ENV PORT=80

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 CMD curl -f http://localhost/api/health || exit 1

# Start script
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]