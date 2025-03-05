# Installation Guide for MV Face Recognition

## Installation Issue with Insightface

The `insightface` package is failing to build on macOS with Python 3.12 due to C++ compilation issues. The specific error is:

```
ld: library 'c++' not found
clang++: error: linker command failed with exit code 1
```

This is happening because the package is trying to use a specific SDK path that doesn't exist on your system:

```
/Applications/Xcode_15.2.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX14.2.sdk
```

## Solution: Using Conda Environment

We've provided two shell scripts to help you set up and run the face recognition code using a Conda environment, which handles these C++ dependencies much better:

1. **setup_conda_env.sh** - Installs Miniconda (if not already installed) and creates a dedicated environment with all needed dependencies
2. **run_face_recognition.sh** - Runs the face recognition code using the Conda environment

### Step 1: Set up the Conda Environment

Run the setup script:

```bash
./setup_conda_env.sh
```

This will:
- Install Miniconda (if not already installed)
- Create a `face_recog` environment with Python 3.9
- Install all necessary dependencies including insightface 0.6.0

The script will take some time to complete as it downloads and installs all dependencies.

### Step 2: Run the Face Recognition Code

After setup is complete, run:

```bash
./run_face_recognition.sh
```

This will activate the Conda environment and run the face recognition code with the specified parameters.

## Alternative Approaches

If you prefer not to use Conda, you could try:

1. Installing a specific version of Xcode that matches the expected SDK path
2. Modifying the insightface build process to use the SDK paths available on your system
3. Using a pre-built insightface wheel if available for your platform

## Troubleshooting

If you encounter issues with the Conda setup:

1. Make sure your shell can find the conda command after installation
2. You may need to restart your terminal after installing Miniconda
3. If you see permission errors, ensure the scripts are executable:
   ```bash
   chmod +x setup_conda_env.sh run_face_recognition.sh
