#!/usr/bin/env python3
"""
Test script to verify the MV Face Recognition system functionality.
"""

import sys
import logging
from pathlib import Path
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_dependencies():
    """Test if all required dependencies are available."""
    logger.info("Testing dependencies...")
    
    try:
        import gradio as gr
        logger.info(f"✓ Gradio {gr.__version__} available")
    except ImportError:
        logger.error("✗ Gradio not available")
        return False
    
    try:
        import cv2
        logger.info(f"✓ OpenCV {cv2.__version__} available")
    except ImportError:
        logger.error("✗ OpenCV not available")
        return False
    
    try:
        import numpy as np
        logger.info(f"✓ NumPy {np.__version__} available")
    except ImportError:
        logger.error("✗ NumPy not available")
        return False
    
    try:
        import pandas as pd
        logger.info(f"✓ Pandas {pd.__version__} available")
    except ImportError:
        logger.error("✗ Pandas not available")
        return False
    
    # Test optional dependencies
    try:
        import insightface
        logger.info("✓ InsightFace available")
    except ImportError:
        logger.warning("⚠ InsightFace not available (face recognition will be limited)")
    
    try:
        import chromadb
        logger.info("✓ ChromaDB available")
    except ImportError:
        logger.warning("⚠ ChromaDB not available (similarity search will be limited)")
    
    return True

def test_file_structure():
    """Test if required files and directories exist."""
    logger.info("Testing file structure...")
    
    required_files = [
        "gradio_app.py",
        "app.py", 
        "batch_process_videos.py",
        "requirements.txt",
        "config.json"
    ]
    
    required_dirs = [
        "src/core",
        "src/services", 
        "src/database",
        "source/videos",
        "source/photo/contestants"
    ]
    
    # Check files
    for file_path in required_files:
        if Path(file_path).exists():
            logger.info(f"✓ {file_path} exists")
        else:
            logger.error(f"✗ {file_path} missing")
            return False
    
    # Check directories
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            logger.info(f"✓ {dir_path}/ exists")
        else:
            logger.error(f"✗ {dir_path}/ missing")
            return False
    
    return True

def test_config():
    """Test configuration file."""
    logger.info("Testing configuration...")
    
    try:
        with open("config.json") as f:
            config = json.load(f)
        
        required_sections = [
            "face_detection",
            "face_matching", 
            "video_processing",
            "paths"
        ]
        
        for section in required_sections:
            if section in config:
                logger.info(f"✓ Config section '{section}' present")
            else:
                logger.error(f"✗ Config section '{section}' missing")
                return False
                
        return True
        
    except Exception as e:
        logger.error(f"✗ Error reading config.json: {e}")
        return False

def test_data_availability():
    """Test if required data is available."""
    logger.info("Testing data availability...")
    
    # Check for videos
    videos_dir = Path("source/videos")
    video_files = list(videos_dir.glob("*.mp4"))
    
    if video_files:
        logger.info(f"✓ Found {len(video_files)} video files")
        for video in video_files[:3]:  # Show first 3
            logger.info(f"  - {video.name}")
    else:
        logger.warning("⚠ No video files found in source/videos/")
    
    # Check for contestant embeddings
    contestants_dir = Path("source/photo/contestants")
    embedding_files = list(contestants_dir.glob("*_embedding.npy"))
    
    if embedding_files:
        logger.info(f"✓ Found {len(embedding_files)} contestant embeddings")
    else:
        logger.warning("⚠ No contestant embeddings found")
    
    return True

def test_gradio_app():
    """Test if Gradio app can be imported and initialized."""
    logger.info("Testing Gradio app...")
    
    try:
        # Add src to path
        sys.path.append('src')
        
        # Try to import the main app
        from gradio_app import GradioMVFaceRecognition
        
        # Try to initialize (without launching)
        app = GradioMVFaceRecognition()
        logger.info("✓ Gradio app can be initialized")
        
        # Test interface creation
        demo = app.create_interface()
        logger.info("✓ Gradio interface can be created")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ Cannot import Gradio app: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Error initializing Gradio app: {e}")
        return False

def test_processing_script():
    """Test if processing script can be imported."""
    logger.info("Testing processing script...")
    
    try:
        # Check if enhanced video processor can be imported
        sys.path.append('src')
        from src.services.enhanced_video_processor import EnhancedVideoProcessor
        
        processor = EnhancedVideoProcessor()
        logger.info("✓ Enhanced video processor can be initialized")
        
        # Test getting available videos
        videos = processor.get_available_videos()
        logger.info(f"✓ Can scan for videos: {len(videos)} found")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ Cannot import video processor: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Error with video processor: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("="*60)
    logger.info("MV FACE RECOGNITION SYSTEM TEST")
    logger.info("="*60)
    
    tests = [
        ("Dependencies", test_dependencies),
        ("File Structure", test_file_structure),
        ("Configuration", test_config),
        ("Data Availability", test_data_availability),
        ("Gradio App", test_gradio_app),
        ("Processing Script", test_processing_script)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n--- Testing {test_name} ---")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"✗ {test_name} test failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nResult: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        logger.info("🎉 All tests passed! System is ready.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)