import cv2
import numpy as np
import onnxruntime
import os


class SegmentationModel:
    def __init__(self, use_fcn: bool = True):
        self.use_fcn = use_fcn

        if self.use_fcn:
            # Initialize FCN ONNX model
            model_path = os.path.join("models", "fcn.onnx")
            if not os.path.exists(model_path):
                raise FileNotFoundError(
                    f"FCN model not found at {model_path}. Please download it first."
                )

            self.session = onnxruntime.InferenceSession(model_path)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name

            # Mean and std for normalization
            self.mean = np.array([0.485, 0.456, 0.406])
            self.std = np.array([0.229, 0.224, 0.225])
        else:
            # Fallback to MediaPipe
            import mediapipe as mp

            self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
            self.segmenter = self.mp_selfie_segmentation.SelfieSegmentation(
                model_selection=1
            )

    def get_person_mask(self, image: np.ndarray) -> np.ndarray:
        if self.use_fcn:
            return self._get_fcn_mask(image)
        else:
            return self._get_mediapipe_mask(image)

    def _get_fcn_mask(self, image: np.ndarray) -> np.ndarray:
        # Preprocess image
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_float = image_rgb.astype(np.float32) / 255.0

        # Normalize
        image_normalized = (image_float - self.mean) / self.std

        # HWC to NCHW format
        image_nchw = np.transpose(image_normalized, (2, 0, 1))
        image_nchw = np.expand_dims(image_nchw, axis=0)

        # Run inference
        outputs = self.session.run([self.output_name], {self.input_name: image_nchw})
        mask = outputs[0][0]  # Take first channel for person class

        # Resize mask to original size if needed
        if mask.shape != image.shape[:2]:
            mask = cv2.resize(mask, (image.shape[1], image.shape[0]))

        return mask > 0.5  # Threshold the mask

    def _get_mediapipe_mask(self, image: np.ndarray) -> np.ndarray:
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Get segmentation mask
        results = self.segmenter.process(image_rgb)

        if results.segmentation_mask is None:
            return np.ones(image.shape[:2], dtype=np.uint8)

        return results.segmentation_mask > 0.1  # Threshold the mask
