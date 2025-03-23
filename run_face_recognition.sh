#!/bin/bash
# Enhanced Face Recognition Wrapper Script
# This script ensures required models are present and runs the face recognition system

set -e  # Exit on error

# Print with colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a model exists
check_model() {
    if [ ! -f "models/$1" ]; then
        echo -e "${YELLOW}Model $1 not found${NC}"
        return 1
    else
        echo -e "${GREEN}✓ Model $1 found${NC}"
        return 0
    fi
}

# Function to display help
display_help() {
    echo -e "${BLUE}Face Recognition System Runner${NC}"
    echo "Usage: $0 [options]"
    echo ""
    echo "This script checks for required models, downloads them if needed,"
    echo "and runs the face recognition system with optimal settings."
    echo ""
    echo "Options:"
    echo "  --help           Display this help message"
    echo "  --download       Force download of models"
    echo "  --tracking       Enable face tracking for faster processing"
    echo "  --in-memory      Use in-memory database (faster but not persistent)"
    echo "  --frame-skip N   Skip N frames (higher value = faster processing)"
    echo "  --save-video     Save labeled output video"
    echo "  --save-frames    Save annotated frames"
    echo "  --debug          Enable debug mode"
    echo ""
    echo "Example:"
    echo "  $0 --tracking --frame-skip 10 --save-video"
}

# Parse arguments
FORCE_DOWNLOAD=0
COMMAND_ARGS=""

for arg in "$@"; do
    case $arg in
        --help)
            display_help
            exit 0
            ;;
        --download)
            FORCE_DOWNLOAD=1
            ;;
        --tracking|--in-memory|--save-video|--save-frames|--debug)
            COMMAND_ARGS="$COMMAND_ARGS $arg"
            ;;
        --frame-skip)
            # Handle --frame-skip parameter with value
            COMMAND_ARGS="$COMMAND_ARGS $arg"
            ;;
        [0-9]*)
            # This assumes the number follows a parameter that requires a value
            COMMAND_ARGS="$COMMAND_ARGS $arg"
            ;;
        *)
            # Any other arguments are passed directly to the Python command
            COMMAND_ARGS="$COMMAND_ARGS $arg"
            ;;
    esac
done

# Print banner
echo -e "${BLUE}=======================================================${NC}"
echo -e "${BLUE}      Optimized Face Recognition System Runner         ${NC}"
echo -e "${BLUE}=======================================================${NC}"
echo ""

# Check for required models
echo -e "${BLUE}Checking required models...${NC}"
MODELS_EXIST=1
check_model "arcface_r50.onnx" || MODELS_EXIST=0
check_model "face_detection_yunet.onnx" || MODELS_EXIST=0

# Download models if needed
if [ $MODELS_EXIST -eq 0 ] || [ $FORCE_DOWNLOAD -eq 1 ]; then
    echo -e "${YELLOW}Downloading required models...${NC}"
    
    # Call the model downloader
    if [ $FORCE_DOWNLOAD -eq 1 ]; then
        python download_models.py --force
    else
        python download_models.py
    fi
    
    # Check if download was successful
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to download models. Please check your internet connection and try again.${NC}"
        exit 1
    fi
fi

# Convert shorthand parameters
FINAL_ARGS=$(echo "$COMMAND_ARGS" | sed 's/--tracking/--use-tracking/g' | sed 's/--in-memory/--in-memory-db/g')

# Run the face recognition system
echo -e "${BLUE}Running face recognition system...${NC}"
echo -e "${YELLOW}Command: python -m src.main $FINAL_ARGS${NC}"
echo ""

# Run the command
python -m src.main $FINAL_ARGS

# Check exit status
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Face recognition completed successfully!${NC}"
    exit 0
else
    echo -e "${RED}Face recognition failed with an error.${NC}"
    exit 1
fi
