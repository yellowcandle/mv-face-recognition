#!/bin/bash

# Detect available SDKs
if [ -d "/Library/Developer/CommandLineTools/SDKs/MacOSX14.sdk" ]; then
    SDK_PATH="/Library/Developer/CommandLineTools/SDKs/MacOSX14.sdk"
elif [ -d "/Library/Developer/CommandLineTools/SDKs/MacOSX14.5.sdk" ]; then
    SDK_PATH="/Library/Developer/CommandLineTools/SDKs/MacOSX14.5.sdk"
elif [ -d "/Library/Developer/CommandLineTools/SDKs/MacOSX15.sdk" ]; then
    SDK_PATH="/Library/Developer/CommandLineTools/SDKs/MacOSX15.sdk"
elif [ -d "/Library/Developer/CommandLineTools/SDKs/MacOSX15.2.sdk" ]; then
    SDK_PATH="/Library/Developer/CommandLineTools/SDKs/MacOSX15.2.sdk"
else
    echo "Could not find a valid SDK. Please ensure Xcode Command Line Tools are installed."
    exit 1
fi

echo "Using SDK at: $SDK_PATH"

# Set environment variables to use the detected Command Line Tools SDK
export SDKROOT=$SDK_PATH
export MACOSX_DEPLOYMENT_TARGET=11.0
export CFLAGS="-I$SDK_PATH/usr/include -stdlib=libc++"
export CXXFLAGS="-I$SDK_PATH/usr/include -stdlib=libc++"
export LDFLAGS="-L$SDK_PATH/usr/lib -stdlib=libc++"
export ARCHFLAGS="-arch arm64"
export CC="/usr/bin/clang"
export CXX="/usr/bin/clang++"

# Detect Python version
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Detected Python version: $PYTHON_VERSION"

# Install dependencies first using pip directly for maximum compatibility
echo "Installing core dependencies..."
pip install -U pip
pip install numpy==1.26.0 scipy scikit-learn scikit-image opencv-python-headless onnx

# For macOS, we need regular onnxruntime (not GPU version) and a specific build for insightface
echo "Installing onnxruntime for macOS..."
pip install onnxruntime

# Try installing insightface using pip directly
echo "Installing insightface with pip..."
pip install insightface

# If that fails, try with specific version and build approach
if [ $? -ne 0 ]; then
    echo "First attempt failed. Trying with direct GitHub installation..."
    pip install git+https://github.com/deepinsight/insightface.git@master
    
    # If still failing, try an older version
    if [ $? -ne 0 ]; then
        echo "Trying older compatible version..."
        pip install insightface==0.7.0
    fi
fi

# Try PP-compatible installation if available
which python -m pip >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "Trying installation with Python project (PP)..."
    python -m pip install --compile insightface
fi

# Check if we have uv available as a fallback
which uv >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "Trying installation with uv as fallback..."
    uv pip install --build insightface
fi

# Verify installation
echo "Verifying installation..."
python -c "import insightface; print(f'Successfully installed insightface {insightface.__version__}')" && \
  echo " Installation successful!" || \
  echo "Installation verification failed. You may need to try a conda environment instead."
