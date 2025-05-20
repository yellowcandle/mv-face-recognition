#!/usr/bin/env python
"""
Run Model Finder Utility

This script runs the model finder utility to discover and download
face recognition and detection models from various sources.

Usage:
    python run_model_finder.py [--force]

Options:
    --force: Force re-download of models even if they exist
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to the path
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import the ModelFinder
try:
    from src.utils.model_finder import ModelFinder
except ImportError:
    print("Error: Could not import ModelFinder. Make sure src/utils/model_finder.py exists.")
    sys.exit(1)


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Run Model Finder to discover face recognition models"
    )
    parser.add_argument("--force", action="store_true", help="Force re-download of models")
    parser.add_argument(
        "--search-packages",
        action="store_true",
        help="Search installed packages for models",
    )
    parser.add_argument(
        "--recognition-only", action="store_true", help="Only find recognition models"
    )
    parser.add_argument("--detection-only", action="store_true", help="Only find detection models")
    args = parser.parse_args()

    print("\n=== Face Recognition Model Finder ===\n")

    # Create ModelFinder instance
    finder = ModelFinder()

    # Determine which model types to find
    model_types = []
    if args.recognition_only:
        model_types = ["face_recognition"]
    elif args.detection_only:
        model_types = ["face_detection"]

    # Find all models of specified types
    print("Searching for available models...")
    models = finder.find_models(model_types)

    # Search packages if requested
    if args.search_packages:
        print("\nSearching installed packages for models...")
        import site

        package_paths = site.getsitepackages()

        # Common model locations
        common_paths = [
            "insightface/models",
            "cv2/data",
            "face_recognition/models",
            "torch/hub/checkpoints",
        ]

        for base_path in package_paths:
            for common_path in common_paths:
                full_path = os.path.join(base_path, common_path)
                if os.path.exists(full_path):
                    print(f"Found model directory: {full_path}")
                    # List files
                    for file in os.listdir(full_path):
                        if file.endswith(
                            (".onnx", ".pb", ".pth", ".caffemodel", ".prototxt", ".bin")
                        ):
                            print(f"  - {file}")

    # Display results
    print("\nDetection Models:")
    detection_count = 0
    for name, path in models.items():
        if "detection" in name:
            print(f"  - {name}: {path}")
            detection_count += 1
    if detection_count == 0:
        print("  (None found)")

    print("\nRecognition Models:")
    recognition_count = 0
    for name, path in models.items():
        if "recognition" in name or "arcface" in name:
            print(f"  - {name}: {path}")
            recognition_count += 1
    if recognition_count == 0:
        print("  (None found)")

    # If no models found or force flag is set, try downloading
    if args.force or (detection_count == 0 and recognition_count == 0):
        print("\nDownloading models...")

        # Try each model in the ModelFinder's MODEL_INFO
        for model_name in finder.MODEL_INFO:
            # Skip if we're only looking for specific types
            if model_types:
                model_type = finder.MODEL_INFO[model_name]["type"]
                if model_type not in model_types:
                    continue

            print(f"Finding model: {model_name}")
            path = finder.find_model(model_name, download_if_missing=True)
            if path:
                print(f"  Success! Model available at: {path}")
            else:
                print(f"  Failed to find or download {model_name}")

    print("\nModel search complete!")

    if detection_count == 0 or recognition_count == 0:
        print("\nWarning: Some model types are missing. Face recognition may not work properly.")
        print("Try running with --force to download all required models.")
    else:
        print("\nAll required models are available. Face recognition should work properly.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
