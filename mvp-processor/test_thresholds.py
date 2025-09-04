#!/usr/bin/env python3
"""
Test different similarity thresholds for face recognition
"""

import yaml
import numpy as np
from main import load_config
from src.video_processing_engine import VideoProcessor, VideoProcessingConfig
from src.face_detection_engine import FaceDetectionEngine
from src.face_recognition_engine import FaceRecognitionEngine

def test_threshold(config, threshold_value):
    """Test a specific threshold value"""
    print(f"\nTesting threshold: {threshold_value}")
    
    # Update config with new threshold
    test_config = config.copy()
    test_config['face_recognition']['similarity_threshold'] = threshold_value
    
    # Create processor with test config
    video_config = VideoProcessingConfig(
        source_path="../source/videos/test-video-mv2.mp4",
        target_path=f"processed_videos/test_threshold_{threshold_value}.mp4",
        confidence_threshold=test_config.get("face_detection", {}).get("min_confidence", 0.5),
        enable_tracking=test_config.get("processing", {}).get("enable_tracking", True),
        enable_smoothing=test_config.get("processing", {}).get("enable_smoothing", True),
    )
    
    processor = VideoProcessor(video_config, full_config=test_config)
    
    # Initialize engines
    face_detector = FaceDetectionEngine(test_config)
    face_recognizer = FaceRecognitionEngine(test_config)
    processor.set_face_detector(face_detector)
    processor.set_face_recognizer(face_recognizer)
    
    try:
        # Process a small number of frames for testing
        print("Processing test video...")
        success = processor.process_video()
        
        if success:
            # Get recognition stats
            recognition_stats = face_recognizer.get_performance_stats()
            summary = processor.get_face_recognition_summary()
            
            print(f"  Success: {success}")
            print(f"  Recognition attempts: {recognition_stats.get('recognition_attempts', 0)}")
            print(f"  Successful recognitions: {recognition_stats.get('successful_recognitions', 0)}")
            print(f"  Success rate: {recognition_stats.get('success_rate', 0):.2%}")
            print(f"  Unique faces recognized: {len(summary)}")
            
            if summary:
                total_recognitions = sum(data["count"] for data in summary.values())
                print(f"  Total recognitions: {total_recognitions}")
                
                # Show top 3 recognized faces
                sorted_recognitions = sorted(
                    summary.items(),
                    key=lambda x: x[1]["count"],
                    reverse=True
                )[:3]
                
                print("  Top recognitions:")
                for contestant_id, data in sorted_recognitions:
                    print(f"    Contestant {contestant_id}: {data['count']} times (avg confidence: {data['avg_confidence']:.3f})")
            
            return recognition_stats.get('success_rate', 0), len(summary), recognition_stats
        else:
            print("  Processing failed")
            return 0, 0, {}
            
    except Exception as e:
        print(f"  Error: {e}")
        return 0, 0, {}
    finally:
        processor.cleanup()

def main():
    """Test multiple threshold values"""
    print("Testing different similarity thresholds...")
    
    # Load base config
    config = load_config()
    
    # Test threshold values
    thresholds = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55]
    results = []
    
    for threshold in thresholds:
        success_rate, unique_faces, stats = test_threshold(config, threshold)
        results.append({
            'threshold': threshold,
            'success_rate': success_rate,
            'unique_faces': unique_faces,
            'stats': stats
        })
    
    # Print summary
    print("\n" + "="*60)
    print("THRESHOLD TESTING SUMMARY")
    print("="*60)
    
    for result in results:
        threshold = result['threshold']
        success_rate = result['success_rate']
        unique_faces = result['unique_faces']
        print(f"Threshold {threshold:.2f}: {success_rate:.2%} success rate, {unique_faces} unique faces")
        
        # Show recommendation if available
        stats = result['stats']
        if 'threshold_analysis' in stats:
            analysis = stats['threshold_analysis']
            recommended = stats.get('recommended_threshold', threshold)
            reason = stats.get('reason', '')
            print(f"  Analysis: {analysis}")
            if recommended != threshold:
                print(f"  Recommended: {recommended:.2f} ({reason})")

if __name__ == "__main__":
    main()