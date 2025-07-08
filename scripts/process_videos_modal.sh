#!/bin/bash

# Modal.com Video Processing Script for MV Face Recognition
# This script processes videos using Modal's cloud infrastructure with GPU acceleration

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
SIMILARITY_THRESHOLD=0.25
FORCE_REPROCESS=false
SINGLE_VIDEO=""
SETUP_MODAL=false
SYNC_DATA=false
DOWNLOAD_RESULTS=false
REFRESH_EMBEDDINGS=false
VOLUME_NAME="mv-face-recognition-data"

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

print_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
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
    echo "  --setup                       Set up Modal.com environment (first-time setup)"
    echo "  --sync-data                   Sync local data to Modal volume"
    echo "  --download-results            Download processed results from Modal volume"
    echo "  --refresh-embeddings          Refresh embeddings and ChromaDB before processing"
    echo "  --volume-name                 Modal volume name (default: mv-face-recognition-data)"
    echo ""
    echo "Examples:"
    echo "  $0 --setup                                  # First-time Modal setup"
    echo "  $0 --sync-data                             # Upload your videos and config to Modal"
    echo "  $0                                          # Process all videos on Modal"
    echo "  $0 -f                                       # Force reprocess all videos"
    echo "  $0 -v \"video.mp4\"                          # Process specific video"
    echo "  $0 -s 0.3 -f                               # Reprocess with higher similarity threshold"
    echo "  $0 --refresh-embeddings                     # Refresh embeddings and ChromaDB before processing"
    echo "  $0 --download-results                       # Download processed files"
    echo ""
    echo "Typical workflow:"
    echo "  1. $0 --setup                               # One-time setup"
    echo "  2. $0 --sync-data                           # Upload your data"
    echo "  3. $0 --refresh-embeddings                  # Refresh embeddings and ChromaDB"
    echo "  4. $0                                       # Process videos"
    echo "  5. $0 --download-results                    # Download results"
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
        --setup)
            SETUP_MODAL=true
            shift
            ;;
        --sync-data)
            SYNC_DATA=true
            shift
            ;;
        --download-results)
            DOWNLOAD_RESULTS=true
            shift
            ;;
        --refresh-embeddings)
            REFRESH_EMBEDDINGS=true
            shift
            ;;
        --volume-name)
            VOLUME_NAME="$2"
            shift 2
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Function to check if modal is installed
check_modal_installed() {
    if ! command -v modal &> /dev/null; then
        print_error "Modal is not installed. Please install it first:"
        echo "pip install modal"
        exit 1
    fi
}

# Function to check if modal is authenticated
check_modal_auth() {
    # Test authentication by trying to list volumes (simplest authenticated command)
    if ! modal volume list &> /dev/null; then
        print_error "Modal is not authenticated. Please run 'modal setup' first."
        exit 1
    fi
}

# Function to setup Modal environment
setup_modal() {
    print_step "Setting up Modal.com environment..."
    
    # Check if modal is installed
    check_modal_installed
    
    # Run modal setup
    print_status "Running Modal setup (this will open a browser for authentication)..."
    modal setup
    
    # Create volume
    print_status "Creating Modal volume: $VOLUME_NAME"
    if modal volume create "$VOLUME_NAME"; then
        print_success "Volume created successfully!"
    else
        print_warning "Volume might already exist, continuing..."
    fi
    
    print_success "Modal setup completed!"
    print_status "Next steps:"
    echo "  1. Run with --sync-data to upload your videos and config"
    echo "  2. Run without flags to process videos"
    echo "  3. Run with --download-results to get processed files"
}

# Function to sync data to Modal volume
sync_data() {
    print_step "Syncing local data to Modal volume..."
    
    check_modal_installed
    check_modal_auth
    
    # Check if source directories exist
    if [ ! -d "source" ]; then
        print_error "Source directory not found. Please run this script from the project root directory."
        exit 1
    fi
    
    if [ ! -f "config.json" ]; then
        print_error "Config file not found. Please run this script from the project root directory."
        exit 1
    fi
    
    # Sync source directory
    print_status "Uploading source directory to Modal volume..."
    if modal volume put "$VOLUME_NAME" ./source /source --force; then
        print_success "Source directory uploaded successfully!"
    else
        print_error "Failed to upload source directory"
        exit 1
    fi
    
    # Sync config file
    print_status "Uploading config.json to Modal volume..."
    if modal volume put "$VOLUME_NAME" ./config.json /config.json --force; then
        print_success "Config file uploaded successfully!"
    else
        print_error "Failed to upload config file"
        exit 1
    fi
    
    print_success "Data sync completed!"
    print_status "Your videos and configuration are now available on Modal's cloud storage."
}

# Function to refresh embeddings and ChromaDB
refresh_embeddings() {
    print_step "Refreshing embeddings and ChromaDB..."
    
    # Check if fix_embeddings.py exists
    if [ ! -f "fix_embeddings.py" ]; then
        print_error "fix_embeddings.py not found. Please run this script from the project root directory."
        exit 1
    fi
    
    # Check if Python environment has required packages
    print_status "Checking Python environment..."
    if ! python3 -c "
import sys
try:
    import numpy as np
    import chromadb
    print('✓ Required packages found')
except ImportError as e:
    print(f'✗ Missing package: {e}')
    sys.exit(1)
"; then
        print_error "Missing required Python packages. Please install requirements:"
        echo "pip install -r requirements.txt"
        exit 1
    fi
    
    # Run the embeddings fix script
    print_status "Running embeddings refresh (this may take a few minutes)..."
    if python3 fix_embeddings.py --all --force; then
        print_success "Embeddings and ChromaDB refreshed successfully!"
    else
        print_error "Failed to refresh embeddings and ChromaDB"
        exit 1
    fi
    
    print_success "Embeddings refresh completed!"
    print_status "Face recognition database is now ready for processing."
}

# Function to download results from Modal volume
download_results() {
    print_step "Downloading processed results from Modal volume..."
    
    check_modal_installed
    check_modal_auth
    
    # Create output directory
    mkdir -p output
    
    # Download processed videos
    print_status "Downloading processed videos..."
    if modal volume get "$VOLUME_NAME" /processed_videos ./output/processed_videos; then
        print_success "Processed videos downloaded!"
    else
        print_warning "No processed videos found or download failed"
    fi
    
    # Download metadata
    print_status "Downloading metadata..."
    if modal volume get "$VOLUME_NAME" /metadata ./output/metadata; then
        print_success "Metadata downloaded!"
    else
        print_warning "No metadata found or download failed"
    fi
    
    # Download clips
    print_status "Downloading clips..."
    if modal volume get "$VOLUME_NAME" /clips ./output/clips; then
        print_success "Clips downloaded!"
    else
        print_warning "No clips found or download failed"
    fi
    
    # Download processing report
    print_status "Downloading processing report..."
    if modal volume get "$VOLUME_NAME" /batch_processing_report.json ./output/batch_processing_report.json; then
        print_success "Processing report downloaded!"
    else
        print_warning "No processing report found or download failed"
    fi
    
    print_success "Download completed!"
    print_status "Downloaded files are available in the 'output' directory."
}

# Function to process videos on Modal
process_videos() {
    print_step "Processing videos on Modal.com..."
    
    check_modal_installed
    check_modal_auth
    
    # Check if modal batch processor exists
    if [ ! -f "scripts/modal_batch_processor.py" ]; then
        print_error "Modal batch processor not found at scripts/modal_batch_processor.py"
        exit 1
    fi
    
    # Build command arguments
    MODAL_ARGS=(
        "scripts/modal_batch_processor.py"
        "--similarity-threshold" "$SIMILARITY_THRESHOLD"
    )
    
    if [ "$FORCE_REPROCESS" = true ]; then
        MODAL_ARGS+=("--force-reprocess")
    fi
    
    if [ -n "$SINGLE_VIDEO" ]; then
        MODAL_ARGS+=("--single-video" "$SINGLE_VIDEO")
    fi
    
    # Print processing configuration
    print_status "Modal Video Processing Configuration:"
    echo "  Volume: $VOLUME_NAME"
    echo "  Similarity threshold: $SIMILARITY_THRESHOLD"
    echo "  Force reprocess: $FORCE_REPROCESS"
    echo "  Single video: ${SINGLE_VIDEO:-"All videos"}"
    echo ""
    
    print_status "Starting Modal video processing..."
    print_warning "This will use Modal's GPU resources. Check your Modal usage dashboard for costs."
    echo ""
    
    # Run the processing
    print_status "Executing: modal run ${MODAL_ARGS[*]}"
    echo ""
    
    if modal run "${MODAL_ARGS[@]}"; then
        print_success "Modal video processing completed successfully!"
        echo ""
        print_status "Next steps:"
        echo "  1. Run with --download-results to get your processed files"
        echo "  2. Check Modal dashboard for processing logs and resource usage"
        echo "  3. Start the backend and frontend to view results in the web interface"
    else
        print_error "Modal video processing failed!"
        exit 1
    fi
}

# Main logic
if [ "$SETUP_MODAL" = true ]; then
    setup_modal
elif [ "$SYNC_DATA" = true ]; then
    sync_data
elif [ "$DOWNLOAD_RESULTS" = true ]; then
    download_results
elif [ "$REFRESH_EMBEDDINGS" = true ]; then
    refresh_embeddings
else
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
    if [ ! -d "scripts" ]; then
        print_error "Scripts directory not found. Please run this script from the project root directory."
        exit 1
    fi
    
    process_videos
fi

print_status "Modal processing script completed!" 