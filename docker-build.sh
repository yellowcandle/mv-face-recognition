#!/bin/bash
# Docker Build Script for MV Face Recognition System

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="mv-face-recognition"
TAG="latest"
DOCKERFILE="Dockerfile"

# Print colored output
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

# Show help
show_help() {
    echo "Docker Build Script for MV Face Recognition System"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  build         Build Docker image"
    echo "  run           Run Docker container"
    echo "  test          Run tests in Docker container"
    echo "  lint          Run linting in Docker container"
    echo "  clean         Clean Docker images and containers"
    echo "  push          Push image to registry"
    echo "  dev           Run development environment"
    echo ""
    echo "Options:"
    echo "  -t, --tag     Set image tag (default: latest)"
    echo "  -f, --file    Dockerfile path (default: Dockerfile)"
    echo "  -h, --help    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build                    # Build with default settings"
    echo "  $0 build -t v1.0.0         # Build with specific tag"
    echo "  $0 run                      # Run the application"
    echo "  $0 test                     # Run tests"
}

# Build Docker image
build_image() {
    print_status "Building Docker image: ${IMAGE_NAME}:${TAG}"
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    # Check if Dockerfile exists
    if [ ! -f "${DOCKERFILE}" ]; then
        print_error "Dockerfile not found: ${DOCKERFILE}"
        exit 1
    fi
    
    # Show build context size
    print_status "Analyzing build context..."
    CONTEXT_SIZE=$(du -sh . | cut -f1)
    print_status "Build context size: ${CONTEXT_SIZE}"
    
    # Check for large files that might slow down build
    LARGE_FILES=$(find . -name "*.mp4" -o -name "*.mkv" -o -name "*.webm" -o -name "*.avi" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$LARGE_FILES" -gt 0 ]; then
        print_warning "Found ${LARGE_FILES} video files. Consider using .dockerignore to exclude them for faster builds."
    fi
    
    # Build with BuildKit for better performance
    export DOCKER_BUILDKIT=1
    print_status "Using Docker BuildKit for optimized builds"
    
    # Build the image with progress tracking
    print_status "Starting Docker build..."
    if docker build \
        --progress=plain \
        --no-cache \
        -t "${IMAGE_NAME}:${TAG}" \
        -f "${DOCKERFILE}" \
        .; then
        
        print_success "Docker image built successfully: ${IMAGE_NAME}:${TAG}"
        
        # Show detailed image information
        print_status "=== Image Information ==="
        SIZE=$(docker image inspect "${IMAGE_NAME}:${TAG}" --format='{{.Size}}' | numfmt --to=iec-i --suffix=B)
        CREATED=$(docker image inspect "${IMAGE_NAME}:${TAG}" --format='{{.Created}}' | cut -d'T' -f1)
        LAYERS=$(docker history "${IMAGE_NAME}:${TAG}" --no-trunc | wc -l | tr -d ' ')
        
        print_status "Image size: ${SIZE}"
        print_status "Created: ${CREATED}"
        print_status "Layers: ${LAYERS}"
        
        # Test health endpoint availability
        print_status "=== Testing Health Endpoint ==="
        if docker run --rm -d --name "${IMAGE_NAME}-health-test" -p 8080:8080 "${IMAGE_NAME}:${TAG}" >/dev/null 2>&1; then
            sleep 10  # Give the container time to start
            if curl -f http://localhost:8080/health >/dev/null 2>&1; then
                print_success "Health endpoint is accessible"
            else
                print_warning "Health endpoint test failed - may need more startup time"
            fi
            docker stop "${IMAGE_NAME}-health-test" >/dev/null 2>&1
        else
            print_warning "Could not start test container for health check"
        fi
        
    else
        print_error "Failed to build Docker image"
        print_error "Check the build logs above for detailed error information"
        exit 1
    fi
}

# Run Docker container
run_container() {
    print_status "Running Docker container: ${IMAGE_NAME}:${TAG}"
    
    # Check if required directories exist
    for dir in source cache output; do
        if [ ! -d "$(pwd)/$dir" ]; then
            print_status "Creating directory: $dir"
            mkdir -p "$(pwd)/$dir"
        fi
    done
    
    print_status "Container will be accessible at:"
    print_status "  - Health check: http://localhost:8080/health"
    print_status "  - Main interface: http://localhost:8081"
    print_status ""
    print_status "Press Ctrl+C to stop the container"
    
    docker run -it --rm \
        --name "${IMAGE_NAME}-app" \
        -p 8080:8080 \
        -p 8081:8081 \
        -v "$(pwd)/source:/app/source:ro" \
        -v "$(pwd)/cache:/app/cache" \
        -v "$(pwd)/output:/app/output" \
        -v "$(pwd)/config.json:/app/config.json:ro" \
        -v "$(pwd)/contestant_info.csv:/app/contestant_info.csv:ro" \
        "${IMAGE_NAME}:${TAG}"
}

# Run tests in Docker
run_tests() {
    print_status "Running tests in Docker container"
    
    docker run --rm \
        -v "$(pwd):/app" \
        -w /app \
        "${IMAGE_NAME}:${TAG}" \
        python -m pytest tests/ -v
}

# Run linting in Docker
run_lint() {
    print_status "Running linting in Docker container"
    
    docker run --rm \
        -v "$(pwd):/app" \
        -w /app \
        "${IMAGE_NAME}:${TAG}" \
        sh -c "ruff check . && black --check ."
}

# Clean Docker resources
clean_docker() {
    print_status "Cleaning Docker resources"
    
    # Remove containers
    if docker ps -a -q --filter ancestor="${IMAGE_NAME}" | grep -q .; then
        print_status "Removing containers..."
        docker rm -f $(docker ps -a -q --filter ancestor="${IMAGE_NAME}")
    fi
    
    # Remove images
    if docker images -q "${IMAGE_NAME}" | grep -q .; then
        print_status "Removing images..."
        docker rmi -f $(docker images -q "${IMAGE_NAME}")
    fi
    
    # Prune unused resources
    docker system prune -f
    
    print_success "Docker cleanup completed"
}

# Development environment
dev_environment() {
    print_status "Starting development environment"
    
    docker run -it --rm \
        -p 8080:8080 \
        -p 7860:7860 \
        -v "$(pwd):/app" \
        -w /app \
        -e GRADIO_SERVER_NAME=0.0.0.0 \
        -e GRADIO_DEBUG=True \
        "${IMAGE_NAME}:${TAG}" \
        bash
}

# Push to registry
push_image() {
    print_status "Pushing image to registry"
    
    if [ -z "$DOCKER_REGISTRY" ]; then
        print_warning "DOCKER_REGISTRY environment variable not set"
        print_status "Using Docker Hub as default registry"
        REGISTRY=""
    else
        REGISTRY="${DOCKER_REGISTRY}/"
    fi
    
    FULL_NAME="${REGISTRY}${IMAGE_NAME}:${TAG}"
    
    docker tag "${IMAGE_NAME}:${TAG}" "${FULL_NAME}"
    docker push "${FULL_NAME}"
    
    print_success "Image pushed: ${FULL_NAME}"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -f|--file)
            DOCKERFILE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        build)
            COMMAND="build"
            shift
            ;;
        run)
            COMMAND="run"
            shift
            ;;
        test)
            COMMAND="test"
            shift
            ;;
        lint)
            COMMAND="lint"
            shift
            ;;
        clean)
            COMMAND="clean"
            shift
            ;;
        push)
            COMMAND="push"
            shift
            ;;
        dev)
            COMMAND="dev"
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Execute command
case "${COMMAND:-build}" in
    build)
        build_image
        ;;
    run)
        run_container
        ;;
    test)
        run_tests
        ;;
    lint)
        run_lint
        ;;
    clean)
        clean_docker
        ;;
    push)
        push_image
        ;;
    dev)
        dev_environment
        ;;
    *)
        print_error "No valid command specified"
        show_help
        exit 1
        ;;
esac