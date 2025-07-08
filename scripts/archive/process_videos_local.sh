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
REFRESH_EMBEDDINGS=false
CONFIG_FILE="config.json"
GENERATE_DENSE_METADATA=true
PARALLEL_PROCESSING=false

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
    echo "  -r, --refresh-embeddings     Refresh embeddings and ChromaDB before processing"
    echo "  --no-dense                   Skip dense metadata generation (faster but less smooth video player)"
    echo "  --parallel                   Enable parallel processing for multiple videos"
    echo "  -c, --config                 Path to config file (default: config.json)"
    echo ""
    echo "Examples:"
    echo "  $0                                          # Process all videos with dense metadata (recommended)"
    echo "  $0 --no-dense                              # Process without dense metadata (faster)"
    echo "  $0 --parallel                              # Process with parallel optimization"
    echo "  $0 -f                                       # Force reprocess all videos"
    echo "  $0 -v \"video.mp4\"                          # Process specific video"
    echo "  $0 -s 0.3 -f                               # Reprocess with higher similarity threshold"
    echo "  $0 -r                                       # Refresh embeddings and ChromaDB before processing"
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
        -r|--refresh-embeddings)
            REFRESH_EMBEDDINGS=true
            shift
            ;;
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --no-dense)
            GENERATE_DENSE_METADATA=false
            shift
            ;;
        --parallel)
            PARALLEL_PROCESSING=true
            shift
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

# Function to refresh embeddings and ChromaDB
refresh_embeddings() {
    print_status "Refreshing embeddings and ChromaDB..."
    
    # Check if fix_embeddings.py exists
    if [ ! -f "fix_embeddings.py" ]; then
        print_error "fix_embeddings.py not found. Please run this script from the project root directory."
        exit 1
    fi
    
    # Check if Python environment has required packages for embeddings refresh
    print_status "Checking Python environment for embeddings refresh..."
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
echo "  Refresh embeddings: $REFRESH_EMBEDDINGS"
echo "  Generate dense metadata: $GENERATE_DENSE_METADATA"
echo "  Parallel processing: $PARALLEL_PROCESSING"
echo "  Dry run: $DRY_RUN"
echo ""

# Refresh embeddings if requested
if [ "$REFRESH_EMBEDDINGS" = true ]; then
    refresh_embeddings
    echo ""
fi

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
        
        # Generate dense metadata for better video player experience
        if [ "$GENERATE_DENSE_METADATA" = true ]; then
            echo ""
            print_status "🚀 Generating dense metadata for smooth video player synchronization..."
            print_warning "This will provide 6x more timeline data for real-time face gallery sync"
            
            # Find processed videos
            if [ -d "processed_videos" ]; then
                video_count=0
                for video in processed_videos/*_annotated.mp4; do
                    if [ -f "$video" ]; then
                        ((video_count++))
                        print_status "Processing dense metadata for $(basename "$video")..."
                        if python3 src/services/realtime_video_processor.py "$video"; then
                            print_success "Dense metadata generated for $(basename "$video")"
                        else
                            print_warning "Failed to generate dense metadata for $(basename "$video")"
                        fi
                    fi
                done
                
                if [ $video_count -gt 0 ]; then
                    print_success "Dense metadata generation completed for $video_count videos!"
                    print_status "Videos now have enhanced timeline data for smooth playback synchronization"
                else
                    print_warning "No processed videos found for dense metadata generation"
                fi
            else
                print_warning "processed_videos directory not found, skipping dense metadata generation"
            fi
        fi
        
        echo ""
        print_status "Output locations:"
        echo "  📹 Processed videos: processed_videos/"
        echo "  📊 Sparse metadata: metadata/*_metadata.json"
        if [ "$GENERATE_DENSE_METADATA" = true ]; then
            echo "  🎯 Dense metadata: metadata/*_dense_metadata.json (6x more timeline data)"
        fi
        echo "  🎬 Clips: clips/"
        echo "  📋 Processing report: batch_processing_report.json"
        echo ""
        print_status "You can now:"
        echo "  1. Review the processing report for detailed statistics"
        echo "  2. Check the processed videos with annotations"
        echo "  3. Analyze the generated clips for specific contestants"
        echo "  4. Start the backend and frontend to view results with enhanced timeline sync"
        echo "     ./scripts/start_app.sh"
    else
        print_success "Dry run completed successfully!"
    fi
else
    print_error "Local video processing failed!"
    exit 1
fi 