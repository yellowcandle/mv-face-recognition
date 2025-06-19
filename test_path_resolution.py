#!/usr/bin/env python3
"""
Test script to verify path resolution in different environments.
This helps debug the videos directory issue in Hugging Face Spaces.
"""

import os
import sys
from pathlib import Path

def test_path_resolution():
    """Test path resolution for videos directory."""
    print("=" * 60)
    print("🔍 Testing Path Resolution")
    print("=" * 60)
    
    # Environment information
    print(f"🌍 Environment:")
    print(f"   Current working directory: {Path.cwd()}")
    print(f"   HF_SPACE_ID: {os.getenv('HF_SPACE_ID', 'Not set')}")
    print(f"   Script location: {Path(__file__).parent}")
    print()
    
    # Test different possible paths
    test_paths = [
        Path.cwd() / "source" / "videos",
        Path("/home/user/app/source/videos"),
        Path("/app/source/videos"),
        Path(__file__).parent / "source" / "videos",
        Path(__file__).parent.parent / "source" / "videos",
    ]
    
    print("🔍 Testing video directory paths:")
    found_paths = []
    
    for i, test_path in enumerate(test_paths, 1):
        exists = test_path.exists()
        status = "✅" if exists else "❌"
        print(f"   {i}. {status} {test_path}")
        
        if exists:
            found_paths.append(test_path)
            # List some files if directory exists
            try:
                video_files = list(test_path.glob("*.mp4"))[:3]  # First 3 MP4 files
                if video_files:
                    print(f"      📹 Found videos: {[f.name for f in video_files]}")
                else:
                    print(f"      📁 Directory exists but no MP4 files found")
            except Exception as e:
                print(f"      ⚠️ Error listing files: {e}")
    
    print()
    
    if found_paths:
        print("✅ Found video directories:")
        for path in found_paths:
            print(f"   📁 {path}")
    else:
        print("❌ No video directories found!")
        print("   Please ensure videos are placed in source/videos/")
    
    print()
    
    # Test project root detection
    print("🔍 Testing project root detection:")
    try:
        from src.config.settings import _get_project_root
        project_root = _get_project_root()
        print(f"   📂 Project root: {project_root}")
        
        # Test if videos directory exists relative to project root
        videos_dir = project_root / "source" / "videos"
        if videos_dir.exists():
            print(f"   ✅ Videos directory found at: {videos_dir}")
        else:
            print(f"   ❌ Videos directory not found at: {videos_dir}")
            
    except ImportError as e:
        print(f"   ⚠️ Could not import settings module: {e}")
    except Exception as e:
        print(f"   ❌ Error in project root detection: {e}")
    
    print()
    print("=" * 60)
    print("🏁 Path resolution test complete")
    print("=" * 60)

if __name__ == "__main__":
    test_path_resolution() 