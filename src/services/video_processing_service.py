import os
import cv2
import numpy as np
import logging
from typing import List, Dict, Any, Tuple
from tqdm import tqdm
import tempfile

from src.core.face_detector import FaceDetector
from src.services.recognition_service import RecognitionService
from src.utils import drawing

logger = logging.getLogger(__name__)

class VideoProcessingService:
    def __init__(self, detector: FaceDetector, recognition_service: RecognitionService):
        self.detector = detector
        self.recognition_service = recognition_service

    def process_video(
        self,
        video_path: str,
        known_embeddings: Dict[str, np.ndarray],
        similarity_threshold: float,
        frame_skip: int,
        enhanced_ui: bool = True,
        progress_callback=None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Processes a video file, produces an annotated video, and returns recognition results.

        Args:
            video_path: Path to the input video.
            known_embeddings: Dictionary of known face embeddings.
            similarity_threshold: Confidence threshold for matching.
            frame_skip: Number of frames to skip between processing.
            enhanced_ui: Whether to use enhanced drawing features.
            progress_callback: A Gradio progress object to update the UI.

        Returns:
            A tuple containing the path to the output video and a list of recognition results.
        """
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None, []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video file: {video_path}")
            return None, []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Ensure dimensions are even for codec compatibility
        width = width if width % 2 == 0 else width - 1
        height = height if height % 2 == 0 else height - 1

        output_path = tempfile.mktemp(suffix=".mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not out.isOpened():
            logger.error("Failed to initialize video writer.")
            cap.release()
            return None, []

        results = []
        frame_count = 0
        label_cache = {}
        persistence_duration = 90  # Frames

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height))

            matches = []
            if frame_count % frame_skip == 0:
                matches = self.process_frame(frame, known_embeddings, similarity_threshold)
                label_cache = self._update_persistent_labels(matches, label_cache, frame_count, persistence_duration)
                
                for face, name, confidence in matches:
                    if name != "Unknown":
                        timestamp = frame_count / fps
                        results.append({
                            "frame": frame_count,
                            "time": f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}",
                            "name": name,
                            "confidence": confidence,
                        })

            timestamp_str = f"{int((frame_count/fps) // 60):02d}:{int((frame_count/fps) % 60):02d}"
            annotated_frame = self.annotate_frame(frame, matches, timestamp_str, label_cache, frame_count, enhanced_ui)
            
            out.write(annotated_frame)

            if progress_callback:
                try:
                    # Gradio 5.x progress update
                    progress_callback(
                        frame_count / total_frames,
                        desc=f"Processing frame {frame_count}/{total_frames}",
                    )
                except Exception as e:
                    # Fallback for different progress callback signatures
                    logger.debug(f"Progress callback error (non-critical): {e}")
                    pass

        cap.release()
        out.release()
        logger.info(f"Finished processing. Annotated video saved to {output_path}")
        return output_path, results

    def get_all_matches_from_video(
        self,
        video_path: str,
        known_embeddings: Dict[str, np.ndarray],
        similarity_threshold: float,
        frame_skip: int,
    ) -> List[Tuple[Any, str, float]]:
        """
        Processes a video to get all face matches without generating an output video.
        Used for data analysis like UMAP.
        """
        if not os.path.exists(video_path):
            return []

        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        all_matches = []

        with tqdm(total=total_frames, desc="Analyzing video for UMAP") as pbar:
            frame_count = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                pbar.update(1)

                if frame_count % frame_skip == 0:
                    matches = self.process_frame(frame, known_embeddings, similarity_threshold)
                    if matches:
                        all_matches.extend(matches)
        
        cap.release()
        return all_matches

    def process_image(
        self,
        image_path: str,
        known_embeddings: Dict[str, np.ndarray],
        similarity_threshold: float,
        enhanced_ui: bool = True,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Processes a single image for face recognition."""
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Could not read image file: {image_path}")
            return None, []

        matches = self.process_frame(image, known_embeddings, similarity_threshold)
        annotated_image = self.annotate_frame(image, matches, enhanced_ui=enhanced_ui)
        
        results = []
        for face, name, confidence in matches:
            results.append({
                "name": name,
                "confidence": confidence,
                "bbox": face.bbox.tolist(),
            })

        return annotated_image, results

    def process_frame(
        self,
        frame: np.ndarray,
        known_embeddings: Dict[str, np.ndarray],
        similarity_threshold: float,
    ) -> List[Tuple[Any, str, float]]:
        """Detects and recognizes faces in a single frame."""
        matches = []
        try:
            faces = self.detector.detect_faces(frame)
            for face in faces:
                embedding = face.normed_embedding
                if embedding is not None:
                    name, confidence = self.recognition_service.match_face(embedding, known_embeddings)
                    if name and confidence >= similarity_threshold:
                        matches.append((face, name, confidence))
        except Exception as e:
            logger.error(f"Error processing frame: {e}", exc_info=True)
        return matches

    def annotate_frame(
        self,
        frame: np.ndarray,
        matches: List[Tuple[Any, str, float]],
        timestamp: str = None,
        persistent_labels: Dict = None,
        current_frame: int = 0,
        enhanced_ui: bool = True,
    ) -> np.ndarray:
        """Draws bounding boxes and labels on a frame using the drawing utility."""
        # This method is now a simplified wrapper around the drawing utility.
        # The complex logic from the original gradio_app.py is now encapsulated there.
        # For this refactoring, we will use a simplified drawing approach.
        # A full implementation would move all drawing logic from gradio_app.py here.
        
        annotated_frame = frame.copy()
        
        for face, name, confidence in matches:
            bbox = face.bbox.astype(int)
            color = (0, 255, 0)
            
            drawing.draw_bounding_box(annotated_frame, bbox, color, padding=5)
            
            label = f"{name} ({confidence:.2f})"
            label_pos = (bbox[0], bbox[1] - 15)
            
            # Use a simple text drawing for now.
            cv2.putText(annotated_frame, label, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        if timestamp:
            annotated_frame = drawing.draw_timestamp(annotated_frame, timestamp)
            
        return annotated_frame

    def _update_persistent_labels(self, matches, label_cache, current_frame, persistence_duration):
        """Placeholder for the label tracking logic that was in gradio_app.py."""
        # This logic can be moved from gradio_app.py to here for full encapsulation.
        # For now, we return an empty cache.
        return {}
