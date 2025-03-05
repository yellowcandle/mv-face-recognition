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

# Try installing with a pre-built wheel first (avoiding compilation)
echo "Trying to install insightface without compilation..."
uv pip install --only-binary=:all: insightface

# If that fails, install the dependencies first
if [ $? -ne 0 ]; then
    echo "Installing dependencies first..."
    uv pip install numpy==1.26.0 scipy scikit-learn scikit-image opencv-python-headless
    uv pip install onnxruntime
    
    # Try installing an older version that might be more compatible
    echo "Attempting to install insightface 0.6.0..."
    uv pip install insightface==0.6.0
fi

# If that fails, try using pip directly
if [ $? -ne 0 ]; then
    echo "Trying with system pip..."
    pip install insightface==0.6.0
fi

# If that also fails, try with a more specific approach
if [ $? -ne 0 ]; then
    echo "Trying alternative installation with modified build settings..."
    pip install Cython
    pip install --no-binary=:all: insightface==0.6.0
fi

# Last resort: try a minimal direct installation that skips some dependencies
if [ $? -ne 0 ]; then
    echo "Trying minimal installation..."
    pip install --no-deps insightface==0.6.0
    echo "Installing basic dependencies separately..."
    pip install onnx opencv-python scikit-image
fi

echo "Installation attempt complete. Please check if insightface is now working."
echo "If not, consider using a Conda environment which may handle the compilation issues better."
