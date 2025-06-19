#!/usr/bin/env python3
"""
Hugging Face Spaces entry point for MV Face Recognition System.
Optimized for Gradio 5.x deployment on Hugging Face Spaces.
"""

import os
import sys
import logging
from pathlib import Path

# Hugging Face Spaces GPU support
try:
    import spaces
    HF_SPACES_GPU = True
    print("✅ ZeroGPU support detected")
except ImportError:
    # Fallback decorator for local development
    def spaces_gpu_decorator(func):
        return func
    spaces = type('spaces', (), {'GPU': spaces_gpu_decorator})()
    HF_SPACES_GPU = False
    print("💻 Running without ZeroGPU support")

# Suppress warnings for cleaner deployment
os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"
os.environ["INSIGHTFACE_DISABLE_LOGGING"] = "1"

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def setup_logging():
    """Configure logging for Hugging Face Spaces."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log")
            if os.access(".", os.W_OK)
            else logging.NullHandler(),
        ],
    )


def check_environment():
    """Check if running environment is suitable."""
    try:
        import gradio
        import cv2
        import torch

        print("✅ Environment check passed")
        print(f"📦 Gradio: {gradio.__version__}")
        print(f"🔧 OpenCV: {cv2.__version__}")
        print(f"⚡ PyTorch: {torch.__version__}")

        # Check for GPU availability
        if torch.cuda.is_available():
            print(f"🚀 CUDA GPU available: {torch.cuda.get_device_name(0)}")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            print("🍎 Apple Silicon GPU available")
        else:
            print("💻 Running on CPU only")

        return True
    except ImportError as e:
        print(f"❌ Environment check failed: {e}")
        return False


def create_demo():
    """Create and return the Gradio demo."""
    try:
        from gradio_app import create_gradio_interface

        print("🌐 Creating Gradio 5.x interface...")
        demo = create_gradio_interface()

        print("✅ Interface created successfully")
        return demo

    except ImportError as e:
        print(f"⚠️ Module import warning: {e}")
        print("🔄 Creating fallback interface...")

        # Fallback minimal interface if imports fail
        import gradio as gr

        with gr.Blocks(
            title="🎬 MV Face Recognition System", theme=gr.themes.Ocean()
        ) as demo:
            gr.HTML("""
            <div style="text-align: center; padding: 50px;">
                <h1>🎬 MV Face Recognition System</h1>
                <p style="font-size: 1.2em; color: #666;">
                    Advanced AI-powered face recognition for video analysis
                </p>
                <div style="margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 10px;">
                    <h3>⚠️ Setup Required</h3>
                    <p>Some dependencies are still loading. Please:</p>
                    <ol style="text-align: left; display: inline-block;">
                        <li>Ensure all required packages are installed</li>
                        <li>Check that the face recognition models are available</li>
                        <li>Restart the application</li>
                    </ol>
                </div>
                <p style="color: #888; margin-top: 30px;">
                    Powered by Gradio 5.x • InsightFace • ChromaDB
                </p>
            </div>
            """)

        return demo


def main():
    """Main entry point for Hugging Face Spaces."""
    print("=" * 60)
    print("🎬 MV Face Recognition System - Gradio 5.x")
    print("=" * 60)

    setup_logging()

    if not check_environment():
        print("⚠️ Environment check failed. Some features may not work.")

    # Setup contestants directory for HF Spaces
    try:
        from setup_contestants import setup_for_hf_spaces
        setup_for_hf_spaces()
    except Exception as e:
        print(f"⚠️ Setup warning: {e}")

    try:
        demo = create_demo()

        # Launch configuration optimized for Hugging Face Spaces
        print("🚀 Launching on Hugging Face Spaces...")
        demo.launch(
            # Hugging Face Spaces configuration
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            debug=False,
            show_error=True,
            quiet=False,
            # Gradio 5.x specific options
            favicon_path=None,
            ssl_verify=False,
            # Performance optimizations
            max_threads=10,
            # Security settings for public deployment
            auth=None,  # Can be configured for private access
        )

    except Exception as e:
        print(f"❌ Failed to launch application: {e}")
        logging.exception("Application launch failed")

        # Emergency fallback
        import gradio as gr

        with gr.Blocks(title="Error - MV Face Recognition") as error_demo:
            gr.HTML(f"""
            <div style="text-align: center; padding: 50px;">
                <h1>⚠️ Application Error</h1>
                <p>The face recognition system encountered an error:</p>
                <code style="background: #f8f9fa; padding: 10px; border-radius: 5px; display: block; margin: 20px 0;">
                    {str(e)}
                </code>
                <p>Please contact the administrator or try again later.</p>
            </div>
            """)

        error_demo.launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    main()
