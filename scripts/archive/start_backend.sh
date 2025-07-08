#!/bin/bash

# Backend Startup Script for MV Face Recognition
# This script starts the FastAPI backend server

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
HOST="0.0.0.0"
PORT="8000"
RELOAD=true
LOG_LEVEL="info"
WORKERS=1
BACKEND_DIR="backend"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help                    Show this help message"
    echo "  --host HOST                   Host to bind to (default: 0.0.0.0)"
    echo "  --port PORT                   Port to bind to (default: 8000)"
    echo "  --no-reload                   Disable auto-reload in development"
    echo "  --log-level LEVEL             Log level (debug, info, warning, error, critical)"
    echo "  --workers N                   Number of worker processes (default: 1)"
    echo "  --production                  Run in production mode (no reload, multiple workers)"
    echo ""
    echo "Examples:"
    echo "  $0                                          # Start with default settings"
    echo "  $0 --port 8080                             # Start on port 8080"
    echo "  $0 --production                            # Start in production mode"
    echo "  $0 --no-reload --workers 4                 # Start with 4 workers, no reload"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --no-reload)
            RELOAD=false
            shift
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --production)
            RELOAD=false
            WORKERS=4
            LOG_LEVEL="warning"
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Function to check if port is available
check_port_available() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_error "Port $port is already in use. Please choose a different port or stop the service using that port."
        exit 1
    fi
}

# Function to check Python environment
check_python_env() {
    print_status "Checking Python environment..."
    
    # Check Python version
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
        print_error "Python 3.8 or higher is required"
        exit 1
    fi
    
    # Check required packages
    if ! python3 -c "
import sys
try:
    import fastapi
    import uvicorn
    import pydantic
    print('✓ FastAPI and dependencies found')
except ImportError as e:
    print(f'✗ Missing package: {e}')
    sys.exit(1)
"; then
        print_error "Missing required packages. Please install backend requirements:"
        echo "cd $BACKEND_DIR && pip install -r requirements.txt"
        exit 1
    fi
}

# Function to check backend directory and files
check_backend_files() {
    print_status "Checking backend files..."
    
    # Check if backend directory exists
    if [ ! -d "$BACKEND_DIR" ]; then
        print_error "Backend directory not found: $BACKEND_DIR"
        print_error "Please run this script from the project root directory."
        exit 1
    fi
    
    # Check if main.py exists
    if [ ! -f "$BACKEND_DIR/main.py" ]; then
        print_error "Backend main.py not found: $BACKEND_DIR/main.py"
        exit 1
    fi
    
    # Check if app directory exists
    if [ ! -d "$BACKEND_DIR/app" ]; then
        print_error "Backend app directory not found: $BACKEND_DIR/app"
        exit 1
    fi
    
    print_success "Backend files found"
}

# Function to check configuration files
check_config_files() {
    print_status "Checking configuration files..."
    
    # Check if config.json exists (for the main application)
    if [ ! -f "config.json" ]; then
        print_warning "Main config.json not found. Some features may not work properly."
    fi
    
    # Check if backend has requirements.txt
    if [ ! -f "$BACKEND_DIR/requirements.txt" ]; then
        print_warning "Backend requirements.txt not found. Dependencies may not be properly installed."
    fi
    
    print_success "Configuration check completed"
}

# Function to set up environment variables
setup_environment() {
    print_status "Setting up environment variables..."
    
    # Set PYTHONPATH to include the backend directory
    export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"
    
    # Set other environment variables if needed
    export BACKEND_HOST="$HOST"
    export BACKEND_PORT="$PORT"
    
    print_success "Environment variables set"
}

# Function to start the backend server
start_backend() {
    print_status "Starting FastAPI backend server..."
    
    # Change to backend directory
    cd "$BACKEND_DIR"
    
    # Build uvicorn command
    UVICORN_ARGS=(
        "main:app"
        "--host" "$HOST"
        "--port" "$PORT"
        "--log-level" "$LOG_LEVEL"
    )
    
    if [ "$RELOAD" = true ]; then
        UVICORN_ARGS+=("--reload")
    fi
    
    if [ "$WORKERS" -gt 1 ] && [ "$RELOAD" = false ]; then
        UVICORN_ARGS+=("--workers" "$WORKERS")
    fi
    
    # Print configuration
    print_status "Backend Server Configuration:"
    echo "  Host: $HOST"
    echo "  Port: $PORT"
    echo "  Reload: $RELOAD"
    echo "  Log Level: $LOG_LEVEL"
    echo "  Workers: $WORKERS"
    echo "  Backend Directory: $BACKEND_DIR"
    echo ""
    
    print_status "Starting server with command: uvicorn ${UVICORN_ARGS[*]}"
    print_success "Backend server will be available at: http://$HOST:$PORT"
    echo ""
    print_status "API Documentation will be available at:"
    echo "  📚 Swagger UI: http://$HOST:$PORT/docs"
    echo "  📋 ReDoc: http://$HOST:$PORT/redoc"
    echo ""
    print_status "Press Ctrl+C to stop the server"
    echo ""
    
    # Start the server
    exec uvicorn "${UVICORN_ARGS[@]}"
}

# Function to handle cleanup on exit
cleanup() {
    print_status "Shutting down backend server..."
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main execution
print_status "🚀 MV Face Recognition Backend Startup"
print_status "======================================="

# Perform all checks
check_port_available "$PORT"
check_python_env
check_backend_files
check_config_files
setup_environment

# Start the backend server
start_backend 