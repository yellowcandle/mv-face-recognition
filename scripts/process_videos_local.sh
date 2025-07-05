#!/bin/bash

# Local Video Processing Script for MV Face Recognition
# This script processes videos locally using your machine's resources

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
SIMILARITY_THRESHOLD=0.25
FORCE_REPROCESS=false
SINGLE_VIDEO=""
DRY_RUN=false
CONFIG_FILE="config.json"

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
    echo "  -s, --similarity-threshold    Set similarity threshold (0.0-1.0, default: 0.25)"
    echo "  -f, --force-reprocess        Force reprocessing of already processed videos"
    echo "  -v, --single-video           Process only a specific video file"
    echo "  -d, --dry-run                Show what would be processed without actually processing"
    echo "  -c, --config                 Path to config file (default: config.json)"
    echo ""
    echo "Examples:"
    echo "  $0                                          # Process all videos with default settings"
    echo "  $0 -f                                       # Force reprocess all videos"
    echo "  $0 -v \"video.mp4\"                          # Process specific video"
    echo "  $0 -s 0.3 -f                               # Reprocess with higher similarity threshold"
    echo "  $0 -d                                       # Dry run to see what would be processed"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -s|--similarity-threshold)
            SIMILARITY_THRESHOLD="$2"
            shift 2
            ;;
        -f|--force-reprocess)
            FORCE_REPROCESS=true
            shift
            ;;
        -v|--single-video)
            SINGLE_VIDEO="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate similarity threshold
if ! python3 -c "
import sys
try:
    threshold = float('$SIMILARITY_THRESHOLD')
    if not 0.0 <= threshold <= 1.0:
        sys.exit(1)
except ValueError:
    sys.exit(1)
"; then
    print_error "Similarity threshold must be a number between 0.0 and 1.0"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "$CONFIG_FILE" ]; then
    print_error "Config file '$CONFIG_FILE' not found. Please run this script from the project root directory."
    exit 1
fi

if [ ! -d "scripts" ]; then
    print_error "Scripts directory not found. Please run this script from the project root directory."
    exit 1
fi

# Check if batch processing script exists
if [ ! -f "scripts/batch_process_videos.py" ]; then
    print_error "Batch processing script not found at scripts/batch_process_videos.py"
    exit 1
fi

# Check if Python environment has required packages
print_status "Checking Python environment..."
if ! python3 -c "
import sys
try:
    import cv2
    import numpy as np
    import tqdm
    print('✓ Required packages found')
except ImportError as e:
    print(f'✗ Missing package: {e}')
    sys.exit(1)
"; then
    print_error "Missing required Python packages. Please install requirements:"
    echo "pip install -r requirements.txt"
    exit 1
fi

# Check if source directories exist
print_status "Checking source directories..."
if [ ! -d "source/videos" ]; then
    print_error "Source videos directory not found at source/videos"
    exit 1
fi

if [ ! -d "source/photo/contestants" ]; then
    print_error "Contestants photos directory not found at source/photo/contestants"
    exit 1
fi

# Check if contestant embeddings exist
EMBEDDING_COUNT=$(find source/photo/contestants -name "*_embedding.npy" 2>/dev/null | wc -l)
if [ "$EMBEDDING_COUNT" -eq 0 ]; then
    print_error "No contestant embeddings found. Please ensure face embeddings are generated first."
    exit 1
fi

print_success "Found $EMBEDDING_COUNT contestant embeddings"

# Build command arguments
PYTHON_ARGS=(
    "scripts/batch_process_videos.py"
    "--config" "$CONFIG_FILE"
    "--similarity-threshold" "$SIMILARITY_THRESHOLD"
)

if [ "$FORCE_REPROCESS" = true ]; then
    PYTHON_ARGS+=("--force-reprocess")
fi

if [ -n "$SINGLE_VIDEO" ]; then
    PYTHON_ARGS+=("--single-video" "$SINGLE_VIDEO")
fi

if [ "$DRY_RUN" = true ]; then
    PYTHON_ARGS+=("--dry-run")
fi

# Print processing configuration
print_status "Local Video Processing Configuration:"
echo "  Config file: $CONFIG_FILE"
echo "  Similarity threshold: $SIMILARITY_THRESHOLD"
echo "  Force reprocess: $FORCE_REPROCESS"
echo "  Single video: ${SINGLE_VIDEO:-"All videos"}"
echo "  Dry run: $DRY_RUN"
echo ""

if [ "$DRY_RUN" = false ]; then
    # Ask for confirmation unless processing single video
    if [ -z "$SINGLE_VIDEO" ]; then
        read -p "Do you want to proceed with local processing? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Processing cancelled."
            exit 0
        fi
    fi

    print_status "Starting local video processing..."
    print_warning "This may take a significant amount of time depending on your hardware and video length."
    echo ""
fi

# Set up Python path to include project root
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Run the processing
print_status "Executing: python3 ${PYTHON_ARGS[*]}"
echo ""

if python3 "${PYTHON_ARGS[@]}"; then
    if [ "$DRY_RUN" = false ]; then
        print_success "Local video processing completed successfully!"
        echo ""
        print_status "Output locations:"
        echo "  📹 Processed videos: processed_videos/"
        echo "  📊 Metadata: metadata/"
        echo "  🎬 Clips: clips/"
        echo "  📋 Processing report: batch_processing_report.json"
        echo ""
        print_status "You can now:"
        echo "  1. Review the processing report for detailed statistics"
        echo "  2. Check the processed videos with annotations"
        echo "  3. Analyze the generated clips for specific contestants"
        echo "  4. Start the backend and frontend to view results in the web interface"
    else
        print_success "Dry run completed successfully!"
    fi
else
    print_error "Local video processing failed!"
    exit 1
fi 