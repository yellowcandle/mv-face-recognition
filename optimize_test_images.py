#!/usr/bin/env python
"""
Optimize and process test images.
This script provides a convenient way to optimize and process test images in the source/images/test directory.
"""

import os
import sys
from pathlib import Path
import argparse
import time

from src.detection.optimized_detector import OptimizedFaceDetector
from src.recognition.optimized_recognizer import OptimizedFaceRecognizer
from src.utils.test_image_optimizer import TestImageOptimizer, optimize_test_images_processing
from src.utils.performance import optimize_test_images

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test Image Optimization Tool")
    
    parser.add_argument("--output-dir", type=str, 
                        help="Directory to save output images (default: output/test_images)")
    parser.add_argument("--skip-preprocessing", action="store_true",
                        help="Skip preprocessing step")
    parser.add_argument("--force-detection", action="store_true",
                        help="Force face detection even if cached results exist")
    parser.add_argument("--parallel", action="store_true",
                        help="Use parallel processing")
    parser.add_argument("--debug", action="store_true",
                        help="Print debug information")
    
    return parser.parse_args()

def main():
    """Main function"""
    start_time = time.time()
    args = parse_args()
    
    # Set up output directory
    project_root = Path(__file__).resolve().parent
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = project_root / "output" / "test_images"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")
    
    # Initialize components with optimized settings for test images
    detector = OptimizedFaceDetector(
        confidence_threshold=0.3,
        skip_frames=0,  # No need for frame skipping with static images
        tracking_duration=0,  # No need for tracking with static images
        model_size=(320, 320),  # Smaller model size for faster processing
        max_workers=4 if args.parallel else 1
    )
    
    recognizer = OptimizedFaceRecognizer(
        face_detector=detector,
        similarity_threshold=0.6,
        use_batch_processing=args.parallel,
        use_quantized_model=True,
        enable_metadata_cache=True,
        cache_dir=str(project_root / "cache"),
        max_workers=4 if args.parallel else 1
    )
    
    # Create optimizer
    optimizer = TestImageOptimizer(
        detector=detector,
        recognizer=recognizer,
        cache_dir=str(project_root / "cache"),
        max_workers=4 if args.parallel else 1
    )
    
    # Preprocess images if not skipped
    if not args.skip_preprocessing:
        print("\n[1/2] Preprocessing test images...")
        preprocessed = optimizer.preprocess_all_test_images()
        print(f"Preprocessed {preprocessed} test images")
    else:
        print("\n[1/2] Skipping preprocessing as requested")
    
    # Process images
    print("\n[2/2] Processing test images...")
    results = optimizer.process_test_images(output_dir=output_dir)
    
    # Print summary
    elapsed = time.time() - start_time
    print(f"\nProcessed {len(results)} test images in {elapsed:.2f} seconds")
    print(f"Results saved to {output_dir}")
    
    # Print detailed results if debug mode
    if args.debug and results:
        print("\nDetailed results:")
        for result in results:
            path = result.get('path', 'Unknown')
            image_results = result.get('result', [])
            print(f"  {os.path.basename(path)}: {len(image_results)} faces")
            for face in image_results:
                if face.get('person_id'):
                    print(f"    - {face['person_id']} ({face['confidence']:.2f})")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())