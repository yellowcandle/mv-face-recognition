import cv2
import numpy as np
import dlib
from typing import Tuple, Optional, List
import os

class PoseRecognition:
    def __init__(self):
        """Initialize dlib's face detector and facial landmark predictor."""
        self.detector = dlib.get_frontal_face_detector()
        predictor_path = os.path.join(os.path.dirname(__file__), "shape_predictor_68_face_landmarks.dat")
        self.predictor = dlib.shape_predictor(predictor_path)
        
        # 3D model points for pose estimation
        self.model_points = np.array([
            (0.0, 0.0, 0.0),             # Nose tip
            (0.0, -330.0, -65.0),        # Chin
            (-225.0, 170.0, -135.0),     # Left eye left corner
            (225.0, 170.0, -135.0),      # Right eye right corner
            (-150.0, -150.0, -125.0),    # Left mouth corner
            (150.0, -150.0, -125.0)      # Right mouth corner
        ]) / 4.5

        # Camera internals
        self.camera_matrix = np.array([
            [1000.0, 0.0, 500.0],
            [0.0, 1000.0, 300.0],
            [0.0, 0.0, 1.0]
        ])
        self.dist_coeffs = np.zeros((4, 1))

    def get_face_landmarks(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract facial landmarks using dlib.
        
        Args:
            image: Input image in BGR format
            
        Returns:
            Normalized landmarks array or None if no face detected
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.detector(gray)
        
        if not faces:
            return None
            
        face = faces[0]  # Use the first detected face
        shape = self.predictor(gray, face)
        landmarks = np.array([[p.x, p.y] for p in shape.parts()])
        
        # Normalize coordinates
        height, width = image.shape[:2]
        landmarks = landmarks.astype('float32')
        landmarks[:, 0] /= width
        landmarks[:, 1] /= height
        
        return landmarks

    def get_pose_angles(self, image: np.ndarray) -> Optional[Tuple[float, float, float]]:
        """
        Calculate head pose angles (pitch, yaw, roll) from the image.
        
        Args:
            image: Input image in BGR format
            
        Returns:
            Tuple of (pitch, yaw, roll) angles in degrees or None if no face detected
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.detector(gray)
        
        if not faces:
            return None
            
        face = faces[0]
        shape = self.predictor(gray, face)
        
        # Get specific facial landmarks for pose estimation
        image_points = np.array([
            (shape.part(30).x, shape.part(30).y),     # Nose tip
            (shape.part(8).x, shape.part(8).y),       # Chin
            (shape.part(36).x, shape.part(36).y),     # Left eye left corner
            (shape.part(45).x, shape.part(45).y),     # Right eye right corner
            (shape.part(48).x, shape.part(48).y),     # Left mouth corner
            (shape.part(54).x, shape.part(54).y)      # Right mouth corner
        ], dtype="double")

        # Solve PnP
        success, rotation_vec, translation_vec = cv2.solvePnP(
            self.model_points, 
            image_points, 
            self.camera_matrix, 
            self.dist_coeffs
        )

        if not success:
            return None

        # Convert rotation vector to rotation matrix
        rotation_mat, _ = cv2.Rodrigues(rotation_vec)
        
        # Get Euler angles
        pitch = np.arctan2(rotation_mat[2][1], rotation_mat[2][2])
        yaw = np.arctan2(-rotation_mat[2][0], np.sqrt(rotation_mat[2][1]**2 + rotation_mat[2][2]**2))
        roll = np.arctan2(rotation_mat[1][0], rotation_mat[0][0])
        
        # Convert to degrees
        pitch = np.degrees(pitch)
        yaw = np.degrees(yaw)
        roll = np.degrees(roll)
        
        return pitch, yaw, roll

    def get_pose_similarity(self, angles1: Tuple[float, float, float], 
                          angles2: Tuple[float, float, float]) -> float:
        """
        Calculate similarity between two head poses.
        
        Args:
            angles1: First set of (pitch, yaw, roll) angles
            angles2: Second set of (pitch, yaw, roll) angles
            
        Returns:
            Similarity score between 0 and 1
        """
        # Convert angles to vectors
        vec1 = np.array(angles1)
        vec2 = np.array(angles2)
        
        # Calculate angle differences
        angle_diffs = np.abs(vec1 - vec2)
        
        # Normalize differences (assuming max difference of 180 degrees)
        normalized_diffs = 1 - (angle_diffs / 180.0)
        
        # Weight the angles (pitch and yaw more important than roll)
        weights = np.array([0.4, 0.4, 0.2])
        weighted_similarity = np.sum(normalized_diffs * weights)
        
        return weighted_similarity

    def get_pose_features(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Get combined pose features from facial landmarks and head pose angles.
        
        Args:
            image: Input image in BGR format
            
        Returns:
            Combined pose feature vector or None if face not detected
        """
        landmarks = self.get_face_landmarks(image)
        angles = self.get_pose_angles(image)
        
        if landmarks is None or angles is None:
            return None
            
        # Flatten landmarks and combine with angles
        landmark_features = landmarks.flatten()
        angle_features = np.array(angles)
        
        # Combine features (normalize landmarks separately from angles)
        landmark_features = landmark_features / np.linalg.norm(landmark_features)
        angle_features = angle_features / np.linalg.norm(angle_features)
        
        return np.concatenate([landmark_features, angle_features])
