#!/bin/bash

# Check if conda environment exists
if ! conda info --envs | grep -q "face_recog"; then
    echo "Conda environment 'face_recog' not found."
    echo "Please run ./setup_conda_env.sh first to set up the environment."
    exit 1
fi

# Activate conda environment and run the face recognition code
echo "Activating conda environment 'face_recog'..."
source activate face_recog

# Run the face recognition code with the parameters
echo "Running face recognition code..."
python -m src.optimized_main --parallel --debug --batch-size 8

# Return to base environment
conda deactivate
