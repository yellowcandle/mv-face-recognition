#!/bin/bash
# Script to run test image optimization with various settings

# Create required directories
mkdir -p cache
mkdir -p output/test_images

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "Python not found, trying python3 instead"
    PYTHON=python3
else
    PYTHON=python
fi

# Display help information
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    echo "Test Image Optimization Script"
    echo "Usage: ./run_test_image_optimization.sh [option]"
    echo ""
    echo "Options:"
    echo "  -f, --fast      Run with fast settings (parallel, cached)"
    echo "  -d, --debug     Run with debug output"
    echo "  -p, --preprocess Only run preprocessing step"
    echo "  -c, --clean     Clean cache and output before running"
    echo "  -h, --help      Show this help message"
    echo ""
    exit 0
fi

# Clean cache and output if requested
if [ "$1" == "-c" ] || [ "$1" == "--clean" ]; then
    echo "Cleaning cache and output directories..."
    rm -rf cache/*
    rm -rf output/test_images/*
    shift
fi

# Run preprocessing only if requested
if [ "$1" == "-p" ] || [ "$1" == "--preprocess" ]; then
    echo "Running preprocessing only..."
    $PYTHON optimize_test_images.py --skip-preprocessing --debug
    exit 0
fi

# Run with fast settings if requested
if [ "$1" == "-f" ] || [ "$1" == "--fast" ]; then
    echo "Running with fast settings..."
    $PYTHON optimize_test_images.py --parallel
    exit 0
fi

# Run with debug output if requested
if [ "$1" == "-d" ] || [ "$1" == "--debug" ]; then
    echo "Running with debug output..."
    $PYTHON optimize_test_images.py --debug
    exit 0
fi

# Default: run with standard settings
echo "Running test image optimization..."
$PYTHON optimize_test_images.py

echo "Done! Check the output/test_images directory for results."