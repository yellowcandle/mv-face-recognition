#!/bin/bash
# Start backend in background
cd /app/backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 &

# Start nginx in foreground
nginx -g "daemon off;"