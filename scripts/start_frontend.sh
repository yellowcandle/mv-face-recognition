#!/bin/bash

# Frontend Startup Script for MV Face Recognition
# This script starts the SvelteKit frontend development server

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
HOST="localhost"
PORT="5173"
OPEN_BROWSER=true
FRONTEND_DIR="frontend-svelte"
BACKEND_URL="http://localhost:8000"
INSTALL_DEPS=false
BUILD_ONLY=false
PREVIEW_MODE=false

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
    echo "  --host HOST                   Host to bind to (default: localhost)"
    echo "  --port PORT                   Port to bind to (default: 5173)"
    echo "  --no-open                     Don't open browser automatically"
    echo "  --backend-url URL             Backend API URL (default: http://localhost:8000)"
    echo "  --install                     Install dependencies before starting"
    echo "  --build                       Build for production instead of dev server"
    echo "  --preview                     Preview production build"
    echo "  --frontend-dir DIR            Frontend directory (default: frontend-svelte)"
    echo ""
    echo "Examples:"
    echo "  $0                                          # Start with default settings"
    echo "  $0 --port 3000                             # Start on port 3000"
    echo "  $0 --install                               # Install dependencies first"
    echo "  $0 --build                                 # Build for production"
    echo "  $0 --preview                               # Preview production build"
    echo "  $0 --backend-url http://api.example.com    # Use different backend URL"
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
        --no-open)
            OPEN_BROWSER=false
            shift
            ;;
        --backend-url)
            BACKEND_URL="$2"
            shift 2
            ;;
        --install)
            INSTALL_DEPS=true
            shift
            ;;
        --build)
            BUILD_ONLY=true
            shift
            ;;
        --preview)
            PREVIEW_MODE=true
            shift
            ;;
        --frontend-dir)
            FRONTEND_DIR="$2"
            shift 2
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

# Function to check Node.js environment
check_node_env() {
    print_status "Checking Node.js environment..."
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install Node.js 18 or higher."
        exit 1
    fi
    
    # Check Node.js version
    NODE_VERSION=$(node --version | cut -d 'v' -f 2 | cut -d '.' -f 1)
    if [ "$NODE_VERSION" -lt 18 ]; then
        print_error "Node.js version 18 or higher is required. Current version: $(node --version)"
        exit 1
    fi
    
    # Check if npm is installed
    if ! command -v npm &> /dev/null; then
        print_error "npm is not installed. Please install npm."
        exit 1
    fi
    
    print_success "Node.js $(node --version) and npm $(npm --version) found"
}

# Function to check frontend directory and files
check_frontend_files() {
    print_status "Checking frontend files..."
    
    # Check if frontend directory exists
    if [ ! -d "$FRONTEND_DIR" ]; then
        print_error "Frontend directory not found: $FRONTEND_DIR"
        print_error "Please run this script from the project root directory."
        exit 1
    fi
    
    # Check if package.json exists
    if [ ! -f "$FRONTEND_DIR/package.json" ]; then
        print_error "Frontend package.json not found: $FRONTEND_DIR/package.json"
        exit 1
    fi
    
    # Check if svelte.config.js exists
    if [ ! -f "$FRONTEND_DIR/svelte.config.js" ]; then
        print_error "Svelte config not found: $FRONTEND_DIR/svelte.config.js"
        exit 1
    fi
    
    print_success "Frontend files found"
}

# Function to check or install dependencies
check_dependencies() {
    print_status "Checking dependencies..."
    
    cd "$FRONTEND_DIR"
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ] || [ "$INSTALL_DEPS" = true ]; then
        print_status "Installing dependencies..."
        
        # Detect package manager
        if [ -f "package-lock.json" ]; then
            PACKAGE_MANAGER="npm"
        elif [ -f "yarn.lock" ]; then
            PACKAGE_MANAGER="yarn"
        elif [ -f "pnpm-lock.yaml" ]; then
            PACKAGE_MANAGER="pnpm"
        else
            PACKAGE_MANAGER="npm"
        fi
        
        print_status "Using package manager: $PACKAGE_MANAGER"
        
        case $PACKAGE_MANAGER in
            npm)
                npm install
                ;;
            yarn)
                yarn install
                ;;
            pnpm)
                pnpm install
                ;;
        esac
        
        print_success "Dependencies installed successfully"
    else
        print_success "Dependencies already installed"
    fi
    
    cd - > /dev/null
}

# Function to check backend connectivity
check_backend_connectivity() {
    print_status "Checking backend connectivity..."
    
    # Extract host and port from backend URL
    BACKEND_HOST=$(echo "$BACKEND_URL" | sed 's|http://||' | sed 's|https://||' | cut -d ':' -f 1)
    BACKEND_PORT=$(echo "$BACKEND_URL" | sed 's|http://||' | sed 's|https://||' | cut -d ':' -f 2 | cut -d '/' -f 1)
    
    # Default to port 80 if no port specified
    if [ "$BACKEND_HOST" = "$BACKEND_PORT" ]; then
        BACKEND_PORT="80"
    fi
    
    # Check if backend is running
    if ! curl -s --max-time 5 "$BACKEND_URL/health" > /dev/null 2>&1; then
        print_warning "Backend is not responding at $BACKEND_URL"
        print_warning "Please ensure the backend is running before starting the frontend."
        print_warning "You can start the backend with: ./scripts/start_backend.sh"
        echo ""
        read -p "Do you want to continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Frontend startup cancelled."
            exit 0
        fi
    else
        print_success "Backend is responding at $BACKEND_URL"
    fi
}

# Function to build the frontend
build_frontend() {
    print_status "Building frontend for production..."
    
    cd "$FRONTEND_DIR"
    
    # Detect package manager
    if [ -f "package-lock.json" ]; then
        PACKAGE_MANAGER="npm"
    elif [ -f "yarn.lock" ]; then
        PACKAGE_MANAGER="yarn"
    elif [ -f "pnpm-lock.yaml" ]; then
        PACKAGE_MANAGER="pnpm"
    else
        PACKAGE_MANAGER="npm"
    fi
    
    case $PACKAGE_MANAGER in
        npm)
            npm run build
            ;;
        yarn)
            yarn build
            ;;
        pnpm)
            pnpm build
            ;;
    esac
    
    print_success "Frontend built successfully!"
    print_status "Build output is in the 'build' directory"
    
    cd - > /dev/null
}

# Function to start the frontend server
start_frontend() {
    print_status "Starting SvelteKit frontend server..."
    
    cd "$FRONTEND_DIR"
    
    # Detect package manager
    if [ -f "package-lock.json" ]; then
        PACKAGE_MANAGER="npm"
    elif [ -f "yarn.lock" ]; then
        PACKAGE_MANAGER="yarn"
    elif [ -f "pnpm-lock.yaml" ]; then
        PACKAGE_MANAGER="pnpm"
    else
        PACKAGE_MANAGER="npm"
    fi
    
    # Set environment variables
    export VITE_API_BASE_URL="$BACKEND_URL/api"
    export VITE_WS_URL="ws://$(echo "$BACKEND_URL" | sed 's|http://||' | sed 's|https://||')/ws"
    
    # Build command based on mode
    if [ "$PREVIEW_MODE" = true ]; then
        CMD="preview"
    else
        CMD="dev"
    fi
    
    # Build command arguments
    case $PACKAGE_MANAGER in
        npm)
            DEV_CMD="npm run $CMD"
            ;;
        yarn)
            DEV_CMD="yarn $CMD"
            ;;
        pnpm)
            DEV_CMD="pnpm $CMD"
            ;;
    esac
    
    # Add host and port options
    if [ "$CMD" = "dev" ]; then
        DEV_CMD="$DEV_CMD --host $HOST --port $PORT"
        if [ "$OPEN_BROWSER" = false ]; then
            DEV_CMD="$DEV_CMD --no-open"
        fi
    fi
    
    # Print configuration
    print_status "Frontend Server Configuration:"
    echo "  Host: $HOST"
    echo "  Port: $PORT"
    echo "  Mode: $CMD"
    echo "  Backend URL: $BACKEND_URL"
    echo "  Package Manager: $PACKAGE_MANAGER"
    echo "  Frontend Directory: $FRONTEND_DIR"
    echo "  Open Browser: $OPEN_BROWSER"
    echo ""
    
    print_status "Starting server with command: $DEV_CMD"
    print_success "Frontend server will be available at: http://$HOST:$PORT"
    echo ""
    print_status "Environment variables:"
    echo "  VITE_API_BASE_URL: $VITE_API_BASE_URL"
    echo "  VITE_WS_URL: $VITE_WS_URL"
    echo ""
    print_status "Press Ctrl+C to stop the server"
    echo ""
    
    # Start the server
    exec $DEV_CMD
}

# Function to handle cleanup on exit
cleanup() {
    print_status "Shutting down frontend server..."
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main execution
print_status "🎨 MV Face Recognition Frontend Startup"
print_status "========================================"

# Perform all checks
check_node_env
check_frontend_files

# Handle different modes
if [ "$BUILD_ONLY" = true ]; then
    check_dependencies
    build_frontend
    exit 0
fi

check_port_available "$PORT"
check_dependencies
check_backend_connectivity

# Start the frontend server
start_frontend 