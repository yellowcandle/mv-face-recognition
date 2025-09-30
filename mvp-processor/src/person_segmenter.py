import numpy as np
import onnxruntime as ort
from typing import List, Optional
from pathlib import Path
import logging

from src.roi import ROI

logger = logging.getLogger(__name__)


class PersonSegmenter:
    def __init__(
        self,
        model_path: str,
        min_person_area: int = 5000,
        expand_ratio: float = 1.2,
        max_rois_per_frame: int = 20,
    ):
        self.model_path = model_path
        self.min_person_area = min_person_area
        self.expand_ratio = expand_ratio
        self.max_rois_per_frame = max_rois_per_frame

        self.session: Optional[ort.InferenceSession] = None
        self.input_shape = (640, 640)

        if Path(model_path).exists():
            try:
                self.session = ort.InferenceSession(
                    model_path,
                    providers=["CPUExecutionProvider"],
                )
                logger.info(f"Loaded ONNX model from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load ONNX model: {e}")
                self.session = None
        else:
            logger.warning(f"Model file not found: {model_path}")
            self.session = None

    def segment(self, frame: np.ndarray) -> List[ROI]:
        if self.session is None:
            return []

        if frame is None or frame.size == 0:
            return []

        if len(frame.shape) != 3 or frame.shape[2] != 3:
            return []

        try:
            frame_height, frame_width = frame.shape[:2]

            blob = self._preprocess(frame)

            outputs = self.session.run(None, {self.session.get_inputs()[0].name: blob})

            rois = self._postprocess(outputs, frame_width, frame_height)

            rois = [roi for roi in rois if roi.area >= self.min_person_area]

            rois = sorted(rois, key=lambda r: r.confidence, reverse=True)

            rois = rois[: self.max_rois_per_frame]

            expanded_rois = [
                roi.expand(self.expand_ratio, frame_width, frame_height) for roi in rois
            ]

            return expanded_rois

        except Exception as e:
            logger.warning(f"Segmentation failed: {e}")
            return []

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        resized = self._letterbox_resize(frame, self.input_shape)

        blob = resized.astype(np.float32) / 255.0

        blob = blob.transpose(2, 0, 1)

        blob = np.expand_dims(blob, axis=0)

        return blob

    def _letterbox_resize(self, image: np.ndarray, target_size: tuple) -> np.ndarray:
        import cv2

        h, w = image.shape[:2]
        target_h, target_w = target_size

        scale = min(target_w / w, target_h / h)

        new_w = int(w * scale)
        new_h = int(h * scale)

        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        top = (target_h - new_h) // 2
        bottom = target_h - new_h - top
        left = (target_w - new_w) // 2
        right = target_w - new_w - left

        padded = cv2.copyMakeBorder(
            resized,
            top,
            bottom,
            left,
            right,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
        )

        return padded

    def _postprocess(
        self, outputs: List[np.ndarray], frame_width: int, frame_height: int
    ) -> List[ROI]:
        rois = []

        detections = outputs[0]

        if len(detections.shape) == 3:
            detections = detections[0]

        if detections.shape[0] > detections.shape[1]:
            detections = detections.T

        for detection in detections:
            if len(detection) < 5:
                continue

            x_center, y_center, width, height = detection[:4]
            confidence = detection[4] if len(detection) > 4 else 0.0

            if confidence < 0.25:
                continue

            scale_x = frame_width / self.input_shape[1]
            scale_y = frame_height / self.input_shape[0]

            x1 = int((x_center - width / 2) * scale_x)
            y1 = int((y_center - height / 2) * scale_y)
            x2 = int((x_center + width / 2) * scale_x)
            y2 = int((y_center + height / 2) * scale_y)

            x1 = max(0, min(x1, frame_width - 1))
            y1 = max(0, min(y1, frame_height - 1))
            x2 = max(0, min(x2, frame_width))
            y2 = max(0, min(y2, frame_height))

            if x2 <= x1 or y2 <= y1:
                continue

            area = (x2 - x1) * (y2 - y1)

            try:
                roi = ROI(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    confidence=float(confidence),
                    area=area,
                )
                rois.append(roi)
            except ValueError:
                continue

        return rois
