#!/bin/bash
# Combined startup script for MV Face Recognition (Backend + Frontend)

echo "🚀 Starting MV Face Recognition System..."
echo "This will start both the backend and frontend servers"
echo ""

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
        echo "   Backend stopped"
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
        echo "   Frontend stopped"
    fi
    echo "✅ All services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Start backend in background
echo "🔧 Starting backend server..."
cd "$SCRIPT_DIR"
./start_backend.sh &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend in background
echo "🎨 Starting frontend server..."
cd "$SCRIPT_DIR"
./start_frontend.sh &
FRONTEND_PID=$!

echo ""
echo "🎉 System started successfully!"
echo "📡 Backend API: http://127.0.0.1:8000"
echo "📊 API docs: http://127.0.0.1:8000/docs"
echo "🌐 Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID