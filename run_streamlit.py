#!/usr/bin/env python3
"""
Streamlit launcher with comprehensive warning suppression.
"""

import os
import sys
import subprocess
import warnings

# Set environment variables to suppress warnings
os.environ['STREAMLIT_LOGGER_LEVEL'] = 'ERROR'
os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'

# Suppress all warnings
warnings.filterwarnings("ignore")

def run_streamlit():
    """Run Streamlit with optimized settings."""
    cmd = [
        sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
        "--logger.level", "error",
        "--client.showErrorDetails", "false",
        "--server.port", "8501",
        "--server.address", "localhost"
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Streamlit app stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running Streamlit: {e}")

if __name__ == "__main__":
    print("🚀 Starting MV Face Recognition (Streamlit)")
    print("📱 App will be available at: http://localhost:8501")
    print("🔇 Warnings suppressed for cleaner output")
    print("-" * 50)
    run_streamlit()