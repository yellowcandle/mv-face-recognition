#!/bin/bash

# Install miniconda if not already installed
if ! command -v conda &> /dev/null; then
    echo "Miniconda not found. Installing..."
    curl -o ~/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh
    bash ~/miniconda.sh -b -p $HOME/miniconda
    rm ~/miniconda.sh
    echo 'export PATH="$HOME/miniconda/bin:$PATH"' >> ~/.zshrc
    source ~/.zshrc
    echo "Miniconda installed."
else
    echo "Miniconda already installed."
fi

# Ensure conda is in the path
export PATH="$HOME/miniconda/bin:$PATH"

# Create a new conda environment for face recognition
echo "Creating conda environment 'face_recog'..."
conda create -y -n face_recog python=3.9

# Activate the environment
echo "Activating conda environment..."
source activate face_recog

# Install dependencies
echo "Installing dependencies..."
conda install -y -c conda-forge numpy opencv
conda install -y -c conda-forge onnxruntime
conda install -y -c conda-forge scikit-learn scikit-image

# Install insightface (using pip inside conda environment)
echo "Installing insightface..."
pip install insightface==0.6.0

echo "Installation complete. To use this environment, run:"
echo "source activate face_recog"
