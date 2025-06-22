#!/usr/bin/env python3
"""
Zeabur deployment entry point for MV Face Recognition System.
Optimized for Gradio 5.x deployment on Zeabur cloud platform.
"""

import os
import sys
import logging
from pathlib import Path

# Standard cloud deployment - no special GPU handling needed
HF_SPACES_GPU = False
print("☁️ Running on Zeabur cloud platform")

# Suppress warnings for cleaner deployment
os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"
os.environ["INSIGHTFACE_DISABLE_LOGGING"] = "1"

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def setup_logging():
    """Configure logging for Zeabur deployment."""
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
        # Try the new dashboard interface first
        from dashboard_gradio import create_dashboard_interface

        print("🌐 Creating Face Recognition Dashboard...")
        demo = create_dashboard_interface()

        print("✅ Dashboard interface created successfully")
        return demo

    except ImportError as e:
        print(f"⚠️ Dashboard import failed: {e}")
        print("🔄 Trying original interface...")
        
        try:
            from src.gradio_app import create_gradio_interface

            print("🌐 Creating Gradio 5.x interface...")
            demo = create_gradio_interface()

            print("✅ Interface created successfully")
            return demo

        except ImportError as e2:
            print(f"⚠️ Module import warning: {e2}")
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
    """Main entry point for Zeabur deployment."""
    print("=" * 60)
    print("🎬 MV Face Recognition System - Zeabur Cloud")
    print("=" * 60)

    setup_logging()

    if not check_environment():
        print("⚠️ Environment check failed. Some features may not work.")

    # Initialize Zeabur environment
    try:
        from pathlib import Path
        
        print("🚀 Initializing Zeabur environment...")
        
        # Check if contestants directory exists with files
        contestants_dir = Path("source/photo/contestants")
        contestants_dir.mkdir(parents=True, exist_ok=True)
        
        jpg_files = list(contestants_dir.glob("**/*.jpg"))
        png_files = list(contestants_dir.glob("**/*.png"))
        npy_files = list(contestants_dir.glob("**/*.npy"))
        total_images = len(jpg_files) + len(png_files)
        
        print(f"📊 Contestants directory status:")
        print(f"   - Images: {total_images} (JPG: {len(jpg_files)}, PNG: {len(png_files)})")
        print(f"   - Embeddings: {len(npy_files)}")
        
        if total_images == 0 and len(npy_files) == 0:
            print("⚠️ No contestants data found - creating fallback system")
            
            # Create numbered directories for the contestant system
            print("📁 Creating numbered contestant directories...")
            for i in range(1, 11):  # Create first 10 contestant slots
                contestant_dir = contestants_dir / str(i)
                contestant_dir.mkdir(exist_ok=True)
                
                # Create a placeholder README in each directory
                readme_content = f"""# Contestant {i}

This directory is ready for contestant photos.

To add a contestant:
1. Upload photos named: {i}-1.jpg, {i}-2.jpg, etc.
2. Or use the web interface to upload photos
3. The system will automatically generate embeddings

Supported formats: JPG, JPEG, PNG
"""
                (contestant_dir / "README.md").write_text(readme_content)
            
            print(f"✅ Created {10} numbered contestant directories for uploads")
            
            # Create a basic contestant_info.csv for the numbered directories
            try:
                import pandas as pd
                
                contestants_data = []
                for i in range(1, 11):
                    contestants_data.append({
                        "編號": i,
                        "暱稱": f"Contestant {i}",
                        "姓名": f"Contestant {i}",
                        "年齡": "Unknown"
                    })
                
                df = pd.DataFrame(contestants_data)
                csv_path = Path("contestant_info.csv")
                df.to_csv(csv_path, index=False)
                print(f"✅ Created basic contestant_info.csv with {len(contestants_data)} entries")
                
            except ImportError:
                # Fallback without pandas
                csv_content = """編號,暱稱,姓名,年齡
1,Contestant 1,Contestant 1,Unknown
2,Contestant 2,Contestant 2,Unknown
3,Contestant 3,Contestant 3,Unknown
4,Contestant 4,Contestant 4,Unknown
5,Contestant 5,Contestant 5,Unknown
6,Contestant 6,Contestant 6,Unknown
7,Contestant 7,Contestant 7,Unknown
8,Contestant 8,Contestant 8,Unknown
9,Contestant 9,Contestant 9,Unknown
10,Contestant 10,Contestant 10,Unknown
"""
                Path("contestant_info.csv").write_text(csv_content, encoding='utf-8')
                print("✅ Created basic contestant_info.csv (without pandas)")
            
            # Also create the sample directory  
            sample_dir = contestants_dir / "sample"
            sample_dir.mkdir(exist_ok=True)
            (sample_dir / "README.txt").write_text("Sample contestant - upload photos via interface")
            
        elif total_images > 0 or len(npy_files) > 0:
            print(f"✅ Found contestants data - {total_images} images, {len(npy_files)} embeddings")
        
        # Initialize video management system (YouTube integration)
        try:
            print("🎬 Initializing video management system...")
            from src.services.video_service import get_video_manager
            
            video_manager = get_video_manager(enable_youtube=True)
            cache_status = video_manager.get_cache_status()
            
            print(f"📊 Video cache status:")
            print(f"   - Total videos in catalog: {cache_status['total_videos']}")
            print(f"   - Cached videos: {cache_status['cached_videos']}")
            print(f"   - Cache directory: {cache_status['cache_directory']}")
            print(f"   - Cache size: {cache_status['cache_size_mb']:.1f} MB")
            
            # Set the global video manager for gradio_app to use
            try:
                import src.gradio_app
                src.gradio_app.video_manager = video_manager
                print("✅ Video manager shared with Gradio interface")
            except Exception as e:
                print(f"⚠️ Failed to share video manager: {e}")
            
            # Download videos for Zeabur if needed
            is_cloud_deploy = os.environ.get('PORT') or os.path.exists('/app')
            if is_cloud_deploy and cache_status['cached_videos'] < cache_status['total_videos']:
                print("💮 Zeabur cloud detected - downloading videos from YouTube...")
                try:
                    # Download with standard quality for cloud deployment
                    downloaded_videos = video_manager.download_all_videos(
                        max_workers=2,  # Better performance on Zeabur
                        quality="720p"   # Standard quality for better UX
                    )
                    print(f"✅ Downloaded {len(downloaded_videos)} videos from YouTube")
                except Exception as e:
                    print(f"⚠️ Video download failed: {e} - will continue without videos")
            
            elif cache_status['cached_videos'] > 0:
                print(f"✅ Found {cache_status['cached_videos']} videos in cache")
            else:
                print("⚠️ No videos available - some features may be limited")
                
        except Exception as e:
            print(f"⚠️ Video system initialization failed: {e}")
            # Fallback: check for any existing video files
            print("🔍 Checking for existing video files...")
            video_dirs = ["source/videos", "source/videos_hf_clean", "source/videos_hf_optimized"]
            total_videos = 0
            
            for video_dir in video_dirs:
                vid_path = Path(video_dir)
                vid_path.mkdir(parents=True, exist_ok=True)
                mp4_count = len(list(vid_path.glob("*.mp4")))
                if mp4_count > 0:
                    print(f"📁 Found {mp4_count} videos in {video_dir}")
                    total_videos += mp4_count
                    
            if total_videos == 0:
                print("⚠️ No video files found - application will work with image uploads only")
        
        # Create other required directories
        for dir_name in ["cache", "output", "output_frames", "output_mp4s"]:
            Path(dir_name).mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB from embeddings package if available
        try:
            embeddings_pkg_path = Path("embeddings_package.json")
            if embeddings_pkg_path.exists():
                print("📦 Initializing ChromaDB from embeddings package...")
                # Import and run the ChromaDB initialization
                from scripts.create_chroma_from_package import initialize_chromadb_from_package
                initialize_chromadb_from_package()
                print("✅ ChromaDB initialized from embeddings package")
            else:
                print("⚠️ No embeddings package found - ChromaDB will be disabled")
        except Exception as e:
            print(f"⚠️ ChromaDB initialization failed: {e} - will fall back to standard search")
        
        # Download fonts if needed for Zeabur
        try:
            font_path = Path("fonts/SourceHanSansTC-VF.ttf")
            if not font_path.exists():
                print("🔤 Downloading fonts for better Chinese text rendering...")
                from scripts.download_fonts import ensure_fonts_available
                if ensure_fonts_available():
                    print("✅ Fonts downloaded successfully")
                else:
                    print("⚠️ Font download failed - using system fonts")
            else:
                print("✅ Custom fonts available")
        except Exception as e:
            print(f"⚠️ Font setup failed: {e} - using system fonts")
        
        print("✅ Zeabur environment initialization complete")
        
    except Exception as e:
        print(f"⚠️ Zeabur initialization warning: {e}")
        # Minimal fallback
        from pathlib import Path
        for dir_name in ["source/photo/contestants", "source/videos", "cache", "output"]:
            Path(dir_name).mkdir(parents=True, exist_ok=True)

    try:
        demo = create_demo()

        # Launch configuration optimized for Zeabur deployment
        port = int(os.environ.get("PORT", os.environ.get("GRADIO_SERVER_PORT", 8080)))
        print(f"🚀 Launching on Zeabur cloud (port {port})...")
        demo.launch(
            # Zeabur cloud configuration
            server_name="0.0.0.0",
            server_port=port,
            share=False,
            debug=False,
            show_error=True,
            quiet=False,
            # Gradio 5.x specific options
            favicon_path=None,
            ssl_verify=False,
            # Performance optimizations for cloud
            max_threads=20,
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

        port = int(os.environ.get("PORT", os.environ.get("GRADIO_SERVER_PORT", 8080)))
        error_demo.launch(server_name="0.0.0.0", server_port=port, share=False)


if __name__ == "__main__":
    main()
