#!/usr/bin/env python3
"""
Quick test to verify Unicode text rendering in bounding boxes
"""

import sys
sys.path.insert(0, 'mvp-processor/src')

import cv2
import numpy as np
from video_processor import FrameProcessor

# Create a test frame
frame = np.zeros((400, 600, 3), dtype=np.uint8)
frame[:] = (50, 50, 50)  # Dark gray background

# Test with Chinese text (contestant nicknames)
test_cases = [
    ((50, 200, 150, 100), "阿妹", 0.95),      # Chinese
    ((50, 500, 150, 400), "精靈", 0.87),      # Chinese
    ((200, 200, 300, 100), "榛綦", 0.92),     # Chinese
    ((200, 500, 300, 400), "Test", 0.88),    # English for comparison
]

print("Testing Unicode text rendering in bounding boxes...")

for i, (location, label, confidence) in enumerate(test_cases):
    try:
        frame = FrameProcessor.draw_face_box(frame, location, label, confidence)
        print(f"✓ Test {i+1}: '{label}' rendered successfully")
    except Exception as e:
        print(f"✗ Test {i+1}: '{label}' failed - {e}")
        import traceback
        traceback.print_exc()

# Save the test result
output_path = "test_unicode_bbox_output.jpg"
cv2.imwrite(output_path, frame)
print(f"\n✓ Test image saved to: {output_path}")
print("  Open this file to verify Chinese characters are displayed correctly (not ????)")
