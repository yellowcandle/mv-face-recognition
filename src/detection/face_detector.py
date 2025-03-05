import cv2
import numpy as np
from typing import List, Tuple
from pathlib import Path
import os

class FaceDetector:
    def __init__(self, confidence_threshold=0.3):  # Lower threshold
        self.confidence_threshold = confidence_threshold
        
        # Load YuNet face detection model
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "models",
            "face_detection_yunet.onnx"
        )
        self.detector = cv2.FaceDetectorYN.create(
            model_path,
            "",
            (640, 640),  # Larger input size for better detection
            self.confidence_threshold
        )

    def detect_faces(self, image):
        """
        Detect faces in an image using YuNet face detector.
        
        Args:
            image: Input image
            
        Returns:
            list: List of bounding boxes in format [x1, y1, x2, y2]
        """
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            
        height, width = image.shape[:2]
        self.detector.setInputSize((width, height))
        
        faces = self.detector.detect(image)[1]
        
        if faces is None:
            return []
            
        # Convert detections to [x1, y1, x2, y2] format
        bboxes = []
        for face in faces:
            if face[14] >= self.confidence_threshold:  # Check confidence
                x1, y1, w, h = face[0], face[1], face[2], face[3]
                bboxes.append([x1, y1, x1 + w, y1 + h])
                
        return bboxes

    def extract_face(self, image, bbox):
        """
        Extract face region from image using bbox.
        
        Args:
            image: Input image
            bbox: Bounding box in format [x1, y1, x2, y2]
            
        Returns:
            numpy.ndarray: Extracted face region
        """
        x1, y1, x2, y2 = map(int, bbox[:4])
        
        # Get face region
        face = image[y1:y2, x1:x2]
        
        # Ensure minimum size
        if face.shape[0] < 64 or face.shape[1] < 64:
            scale = 64 / min(face.shape[0], face.shape[1])
            face = cv2.resize(face, None, fx=scale, fy=scale)
            
        return face
