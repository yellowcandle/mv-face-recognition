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
COPY <<EOF /etc/nginx/sites-available/default
server {
    listen 80;
    server_name localhost;

    # Serve frontend
    location / {
        root /app/frontend/dist;
        try_files \$uri \$uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }

    # Proxy WebSocket requests
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }
}
EOF

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
COPY <<EOF /start.sh
#!/bin/bash
# Start backend in background
cd /app/backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 &

# Start nginx in foreground
nginx -g "daemon off;"
EOF

RUN chmod +x /start.sh

CMD ["/start.sh"]