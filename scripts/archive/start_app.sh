#!/bin/bash

# Combined Application Startup Script for MV Face Recognition
# This script starts both the backend and frontend servers

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
BACKEND_HOST="0.0.0.0"
BACKEND_PORT="8000"
FRONTEND_HOST="localhost"
FRONTEND_PORT="5173"
WAIT_FOR_BACKEND=true
INSTALL_DEPS=false
START_BACKEND=true
START_FRONTEND=true
BACKEND_ONLY=false
FRONTEND_ONLY=false
PRODUCTION_MODE=false

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

print_backend() {
    echo -e "${PURPLE}[BACKEND]${NC} $1"
}

print_frontend() {
    echo -e "${CYAN}[FRONTEND]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help                    Show this help message"
    echo "  --backend-host HOST           Backend host (default: 0.0.0.0)"
    echo "  --backend-port PORT           Backend port (default: 8000)"
    echo "  --frontend-host HOST          Frontend host (default: localhost)"
    echo "  --frontend-port PORT          Frontend port (default: 5173)"
    echo "  --install                     Install dependencies before starting"
    echo "  --backend-only                Start only the backend server"
    echo "  --frontend-only               Start only the frontend server"
    echo "  --no-wait                     Don't wait for backend to be ready"
    echo "  --production                  Start in production mode"
    echo ""
    echo "Examples:"
    echo "  $0                                          # Start both servers with default settings"
    echo "  $0 --backend-only                          # Start only backend"
    echo "  $0 --frontend-only                         # Start only frontend"
    echo "  $0 --install                               # Install dependencies first"
    echo "  $0 --production                            # Start in production mode"
    echo "  $0 --backend-port 8080 --frontend-port 3000   # Use custom ports"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        --backend-host)
            BACKEND_HOST="$2"
            shift 2
            ;;
        --backend-port)
            BACKEND_PORT="$2"
            shift 2
            ;;
        --frontend-host)
            FRONTEND_HOST="$2"
            shift 2
            ;;
        --frontend-port)
            FRONTEND_PORT="$2"
            shift 2
            ;;
        --install)
            INSTALL_DEPS=true
            shift
            ;;
        --backend-only)
            BACKEND_ONLY=true
            START_FRONTEND=false
            shift
            ;;
        --frontend-only)
            FRONTEND_ONLY=true
            START_BACKEND=false
            shift
            ;;
        --no-wait)
            WAIT_FOR_BACKEND=false
            shift
            ;;
        --production)
            PRODUCTION_MODE=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Function to check if required scripts exist
check_scripts() {
    print_status "Checking required scripts..."
    
    if [ ! -f "scripts/start_backend.sh" ]; then
        print_error "Backend startup script not found: scripts/start_backend.sh"
        exit 1
    fi
    
    if [ ! -f "scripts/start_frontend.sh" ]; then
        print_error "Frontend startup script not found: scripts/start_frontend.sh"
        exit 1
    fi
    
    print_success "Required scripts found"
}

# Function to make scripts executable
make_scripts_executable() {
    print_status "Making scripts executable..."
    chmod +x scripts/start_backend.sh
    chmod +x scripts/start_frontend.sh
    print_success "Scripts are now executable"
}

# Function to check if ports are available
check_ports() {
    print_status "Checking port availability..."
    
    if [ "$START_BACKEND" = true ]; then
        if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_error "Backend port $BACKEND_PORT is already in use"
            exit 1
        fi
    fi
    
    if [ "$START_FRONTEND" = true ]; then
        if lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_error "Frontend port $FRONTEND_PORT is already in use"
            exit 1
        fi
    fi
    
    print_success "Ports are available"
}

# Function to wait for backend to be ready
wait_for_backend() {
    if [ "$WAIT_FOR_BACKEND" = false ]; then
        return 0
    fi
    
    print_status "Waiting for backend to be ready..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s --max-time 2 "http://$BACKEND_HOST:$BACKEND_PORT/health" > /dev/null 2>&1; then
            print_success "Backend is ready!"
            return 0
        fi
        
        print_status "Attempt $attempt/$max_attempts: Backend not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "Backend failed to start within expected time"
    return 1
}

# Function to start backend server
start_backend() {
    print_backend "Starting backend server..."
    
    # Build backend command
    BACKEND_CMD="./scripts/start_backend.sh --host $BACKEND_HOST --port $BACKEND_PORT"
    
    if [ "$PRODUCTION_MODE" = true ]; then
        BACKEND_CMD="$BACKEND_CMD --production"
    fi
    
    print_backend "Command: $BACKEND_CMD"
    
    # Start backend in background
    $BACKEND_CMD &
    BACKEND_PID=$!
    
    print_backend "Backend started with PID: $BACKEND_PID"
    
    # Wait for backend to be ready if we're also starting frontend
    if [ "$START_FRONTEND" = true ]; then
        if wait_for_backend; then
            print_backend "Backend is ready for frontend connection"
        else
            print_error "Backend startup failed"
            kill $BACKEND_PID 2>/dev/null || true
            exit 1
        fi
    fi
}

# Function to start frontend server
start_frontend() {
    print_frontend "Starting frontend server..."
    
    # Build frontend command
    FRONTEND_CMD="./scripts/start_frontend.sh --host $FRONTEND_HOST --port $FRONTEND_PORT"
    FRONTEND_CMD="$FRONTEND_CMD --backend-url http://$BACKEND_HOST:$BACKEND_PORT"
    
    if [ "$INSTALL_DEPS" = true ]; then
        FRONTEND_CMD="$FRONTEND_CMD --install"
    fi
    
    if [ "$PRODUCTION_MODE" = true ]; then
        FRONTEND_CMD="$FRONTEND_CMD --build"
    fi
    
    print_frontend "Command: $FRONTEND_CMD"
    
    # Start frontend
    $FRONTEND_CMD &
    FRONTEND_PID=$!
    
    print_frontend "Frontend started with PID: $FRONTEND_PID"
}

# Function to install dependencies
install_dependencies() {
    if [ "$INSTALL_DEPS" = false ]; then
        return 0
    fi
    
    print_status "Installing dependencies..."
    
    # Install Python dependencies
    if [ "$START_BACKEND" = true ]; then
        print_backend "Installing Python dependencies..."
        if [ -f "requirements.txt" ]; then
            pip install -r requirements.txt
        fi
        if [ -f "backend/requirements.txt" ]; then
            pip install -r backend/requirements.txt
        fi
    fi
    
    # Install Node.js dependencies
    if [ "$START_FRONTEND" = true ]; then
        print_frontend "Installing Node.js dependencies..."
        if [ -d "frontend-svelte" ]; then
            cd frontend-svelte
            npm install
            cd ..
        fi
    fi
    
    print_success "Dependencies installed"
}

# Function to handle cleanup on exit
cleanup() {
    print_status "Shutting down servers..."
    
    # Kill backend if it was started
    if [ -n "$BACKEND_PID" ]; then
        print_backend "Stopping backend server (PID: $BACKEND_PID)"
        kill $BACKEND_PID 2>/dev/null || true
    fi
    
    # Kill frontend if it was started
    if [ -n "$FRONTEND_PID" ]; then
        print_frontend "Stopping frontend server (PID: $FRONTEND_PID)"
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    # Wait a moment for processes to stop
    sleep 2
    
    # Force kill if processes are still running
    if [ -n "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        print_backend "Force stopping backend server"
        kill -9 $BACKEND_PID 2>/dev/null || true
    fi
    
    if [ -n "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        print_frontend "Force stopping frontend server"
        kill -9 $FRONTEND_PID 2>/dev/null || true
    fi
    
    print_success "Application stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main execution
print_status "🚀 MV Face Recognition Application Startup"
print_status "==========================================="

# Print configuration
print_status "Configuration:"
echo "  Backend: $BACKEND_HOST:$BACKEND_PORT"
echo "  Frontend: $FRONTEND_HOST:$FRONTEND_PORT"
echo "  Start Backend: $START_BACKEND"
echo "  Start Frontend: $START_FRONTEND"
echo "  Install Dependencies: $INSTALL_DEPS"
echo "  Production Mode: $PRODUCTION_MODE"
echo ""

# Perform checks
check_scripts
make_scripts_executable
check_ports
install_dependencies

# Start servers
if [ "$START_BACKEND" = true ]; then
    start_backend
fi

if [ "$START_FRONTEND" = true ]; then
    start_frontend
fi

# Print final status
print_success "Application started successfully!"
echo ""
print_status "🌐 Access URLs:"
if [ "$START_BACKEND" = true ]; then
    echo "  📡 Backend API: http://$BACKEND_HOST:$BACKEND_PORT"
    echo "  📚 API Documentation: http://$BACKEND_HOST:$BACKEND_PORT/docs"
fi
if [ "$START_FRONTEND" = true ]; then
    echo "  🎨 Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
fi
echo ""
print_status "Press Ctrl+C to stop all servers"

# Wait for processes to complete
if [ "$START_BACKEND" = true ] && [ "$START_FRONTEND" = true ]; then
    # Wait for either process to exit
    wait $BACKEND_PID $FRONTEND_PID
elif [ "$START_BACKEND" = true ]; then
    wait $BACKEND_PID
elif [ "$START_FRONTEND" = true ]; then
    wait $FRONTEND_PID
fi

# Cleanup will be called automatically by signal handler 