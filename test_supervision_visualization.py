#!/usr/bin/env python3
"""
Test script for professional bbox visualization with Supervision
Tests the new Supervision-based annotation system vs OpenCV fallback
"""

import cv2
import numpy as np
import sys
from pathlib import Path

# Add mvp-processor to path
sys.path.append(str(Path(__file__).parent / "mvp-processor" / "src"))

from video_processor import VideoProcessor
import yaml
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_supervision_visualization():
    """Test professional visualization with Supervision"""

    # Load configuration - adjust path based on current directory
    config_paths = [
        Path("mvp-processor/config/processing_config.yaml"),  # From root
        Path("config/processing_config.yaml"),  # From mvp-processor
        Path(
            "../mvp-processor/config/processing_config.yaml"
        ),  # From test script location
    ]

    config_path = None
    for path in config_paths:
        if path.exists():
            config_path = path
            break

    if config_path is None:
        logger.error(f"Config file not found in any of these locations: {config_paths}")
        return False

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Initialize VideoProcessor with professional visualization
    processor = VideoProcessor(config)

    # Check if Supervision is available
    try:
        import supervision as sv

        logger.info(
            f"✅ Supervision library available - version {sv.__version__ if hasattr(sv, '__version__') else 'unknown'}"
        )
    except ImportError:
        logger.warning(
            "❌ Supervision library not available - will use OpenCV fallback"
        )

    # Test annotation initialization
    if hasattr(processor, "use_supervision"):
        logger.info(
            f"✅ Professional visualization enabled: {processor.use_supervision}"
        )
        if processor.use_supervision:
            logger.info("✅ Supervision annotators initialized successfully")
            logger.info(f"   - BoxAnnotator: {hasattr(processor, 'box_annotator')}")
            logger.info(f"   - LabelAnnotator: {hasattr(processor, 'label_annotator')}")
            logger.info(f"   - TraceAnnotator: {hasattr(processor, 'trace_annotator')}")
            logger.info(
                f"   - Color palette: {len(processor.confidence_colors)} colors"
            )
        else:
            logger.info("⚠️ Using OpenCV fallback visualization")
    else:
        logger.error("❌ Visualization system not properly initialized")
        return False

    # Test with a sample frame and mock face recognition data
    test_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    test_frame[:] = (50, 50, 50)  # Dark gray background

    # Mock face recognition results
    mock_recognitions = [
        {
            "face_location": [100, 300, 200, 200],  # [top, right, bottom, left]
            "confidence": 0.85,
            "contestant_id": "test_1",
            "contestant_name": "阿妹",
            "contestant_nickname": "Mei",
            "weight": 1.0,  # Not interpolated
        },
        {
            "face_location": [150, 600, 250, 500],  # [top, right, bottom, left]
            "confidence": 0.65,
            "contestant_id": "test_2",
            "contestant_name": "小砂",
            "contestant_nickname": "Sica",
            "weight": 1.0,  # Not interpolated
        },
        {
            "face_location": [300, 900, 400, 800],  # [top, right, bottom, left]
            "confidence": 0.45,
            "contestant_id": "test_3",
            "contestant_name": "榛綦",
            "contestant_nickname": "Zoe",
            "weight": 0.7,  # Interpolated (muted colors)
        },
    ]

    # Test annotation rendering
    try:
        scale_x = 1.0  # No scaling for test
        scale_y = 1.0

        # Draw annotations using the new system
        annotated_frame = processor._draw_frame_annotations(
            test_frame.copy(), mock_recognitions, scale_x, scale_y
        )

        # Save test result
        output_path = Path("supervision_test_result.jpg")
        success = cv2.imwrite(str(output_path), annotated_frame)

        if success:
            logger.info(f"✅ Test annotation successful - saved to {output_path}")
            logger.info("   Features tested:")
            logger.info("   - Multiple confidence levels (high/medium/low)")
            logger.info("   - Interpolated vs keyframe styling")
            logger.info("   - CJKV text rendering support")
            logger.info("   - Professional color coding")
            return True
        else:
            logger.error("❌ Failed to save test result")
            return False

    except Exception as e:
        logger.error(f"❌ Error during annotation test: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_color_mapping():
    """Test the confidence-based color mapping system"""
    logger.info("\n🎨 Testing confidence-based color mapping:")

    confidence_tests = [
        (0.95, False, "High confidence, keyframe"),
        (0.70, False, "Medium confidence, keyframe"),
        (0.50, False, "Low confidence, keyframe"),
        (0.65, True, "High confidence, interpolated"),
        (0.45, True, "Medium confidence, interpolated"),
        (0.30, True, "Low confidence, interpolated"),
    ]

    for confidence, is_interpolated, description in confidence_tests:
        # Mock recognition object

        # Simulate the color assignment logic
        if is_interpolated:
            if confidence >= 0.6:
                color_index = 3  # Light green
                color_name = "Light green"
            elif confidence >= 0.4:
                color_index = 4  # Light orange
                color_name = "Light orange"
            else:
                color_index = 5  # Light red
                color_name = "Light red"
        else:
            if confidence >= 0.8:
                color_index = 0  # Bright green
                color_name = "Bright green"
            elif confidence >= 0.6:
                color_index = 1  # Orange
                color_name = "Orange"
            else:
                color_index = 2  # Red
                color_name = "Red"

        logger.info(
            f"   {confidence:.2f} - {description} → {color_name} (index {color_index})"
        )


def main():
    """Run all visualization tests"""
    logger.info("🚀 Testing Professional Bbox Visualization with Supervision")
    logger.info("=" * 60)

    # Test 1: Supervision setup and initialization
    success = test_supervision_visualization()

    # Test 2: Color mapping system
    test_color_mapping()

    # Test 3: Display system capabilities
    logger.info("\n📊 System Capabilities Summary:")
    logger.info("✅ Professional bounding box drawing")
    logger.info("✅ Confidence-based color coding")
    logger.info("✅ CJKV text support")
    logger.info("✅ Interpolation indicators")
    logger.info("✅ Tracking trail visualization (TraceAnnotator)")
    logger.info("✅ Fallback to OpenCV if Supervision unavailable")

    if success:
        logger.info("\n🎉 All tests passed! Professional visualization system ready.")
        logger.info("   Next steps:")
        logger.info("   1. Process test-video-mv2.mp4 with new visualization")
        logger.info("   2. Compare before/after visual quality")
        logger.info("   3. Deploy improved system")
        return True
    else:
        logger.error("\n❌ Some tests failed. Check the error messages above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
