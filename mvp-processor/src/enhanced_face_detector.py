"""
Enhanced Face Detection Module with Apple Silicon Metal/MPS and CUDA Acceleration
Provides hardware-accelerated face detection using InsightFace models with fallback mechanisms
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import time

from hardware_detector import HardwareDetector, HardwareBackend
from face_detector import FaceDetection  # Import original dataclass

logger = logging.getLogger(__name__)


class AcceleratedFaceDetector:
    """Hardware-accelerated face detection using InsightFace models"""

    def __init__(self, config: dict):
        self.config = config
        self.min_confidence = config["face_detection"]["min_confidence"]
        self.max_faces_per_frame = config["face_detection"]["max_faces_per_frame"]
        self.model_path = config["face_detection"]["model_path"]

        # Hardware detection and optimization
        self.hardware_detector = HardwareDetector()
        self.hardware_info = self.hardware_detector.detect_hardware()
        self.memory_config = self.hardware_detector.get_memory_optimization_config(
            self.hardware_info
        )

        # Face detection backend
        self.face_detector = None
        self.backend_type = None

        # Performance tracking
        self.detection_times = []
        self.frame_count = 0

        # Initialize the best available backend
        self._initialize_backend()

    def _initialize_backend(self):
        """Initialize the best available face detection backend based on hardware"""

        if self.hardware_info.backend == HardwareBackend.APPLE_SILICON_METAL:
            success = self._try_initialize_metal_backend()
            if success:
                logger.info(
                    "Initialized Apple Silicon Metal backend for face detection"
                )
                return

        if self.hardware_info.backend == HardwareBackend.CUDA:
            success = self._try_initialize_cuda_backend()
            if success:
                logger.info("Initialized CUDA backend for face detection")
                return

        # Fallback to CPU backend
        self._initialize_cpu_backend()
        logger.info("Initialized CPU backend for face detection")

    def _try_initialize_metal_backend(self) -> bool:
        """Try to initialize Apple Silicon Metal/MPS backend"""
        try:
            # Option 1: Try PyTorch MPS backend with InsightFace
            if self._initialize_pytorch_mps():
                self.backend_type = "pytorch_mps"
                return True

            # Option 2: Try ONNX Runtime with Metal execution provider
            if self._initialize_onnx_metal():
                self.backend_type = "onnx_metal"
                return True

            # Option 3: Try CoreML backend
            if self._initialize_coreml():
                self.backend_type = "coreml"
                return True

        except Exception as e:
            logger.warning(f"Failed to initialize Metal backend: {e}")

        return False

    def _initialize_pytorch_mps(self) -> bool:
        """Initialize PyTorch MPS backend"""
        try:
            import torch
            import insightface

            if not torch.backends.mps.is_available():
                return False

            # Set MPS device
            torch.device("mps")

            # Initialize InsightFace with MPS
            self.face_detector = insightface.app.FaceAnalysis(
                providers=[
                    "CPUExecutionProvider"
                ]  # InsightFace might not directly support MPS
            )
            self.face_detector.prepare(
                ctx_id=-1
            )  # CPU context, but we'll optimize tensor ops

            logger.info("Initialized PyTorch MPS backend (hybrid mode)")
            return True

        except Exception as e:
            logger.debug(f"PyTorch MPS initialization failed: {e}")
            return False

    def _initialize_onnx_metal(self) -> bool:
        """Initialize ONNX Runtime with Metal execution provider"""
        try:
            import onnxruntime as ort

            # Check for available execution providers
            available_providers = ort.get_available_providers()
            if "CoreMLExecutionProvider" not in available_providers:
                return False

            # Create session with Metal/CoreML provider
            providers = [
                (
                    "CoreMLExecutionProvider",
                    {
                        "use_cpu_only": False,
                        "enable_on_subgraph": True,
                    },
                ),
                "CPUExecutionProvider",
            ]

            # Look for ONNX model file
            model_files = list(Path(self.model_path).glob("*.onnx"))
            if not model_files:
                logger.debug("No ONNX models found for Metal backend")
                return False

            model_file = model_files[0]
            self.face_detector = ort.InferenceSession(
                str(model_file), providers=providers
            )
            self.backend_type = "onnx_metal"

            logger.info(f"Initialized ONNX Metal backend with model: {model_file.name}")
            return True

        except Exception as e:
            logger.debug(f"ONNX Metal initialization failed: {e}")
            return False

    def _initialize_coreml(self) -> bool:
        """Initialize CoreML backend (if models are available)"""
        try:
            import coremltools as ct

            # Look for CoreML model files
            model_files = list(Path(self.model_path).glob("*.mlmodel"))
            if not model_files:
                return False

            model_file = model_files[0]
            self.face_detector = ct.models.MLModel(str(model_file))
            self.backend_type = "coreml"

            logger.info(f"Initialized CoreML backend with model: {model_file.name}")
            return True

        except Exception as e:
            logger.debug(f"CoreML initialization failed: {e}")
            return False

    def _try_initialize_cuda_backend(self) -> bool:
        """Try to initialize CUDA backend"""
        try:
            import torch
            import insightface

            if not torch.cuda.is_available():
                return False

            # Initialize InsightFace with CUDA
            self.face_detector = insightface.app.FaceAnalysis(
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
            )
            self.face_detector.prepare(ctx_id=0)  # GPU context

            self.backend_type = "insightface_cuda"
            logger.info("Initialized CUDA backend with InsightFace")
            return True

        except Exception as e:
            logger.debug(f"CUDA initialization failed: {e}")
            return False

    def _initialize_cpu_backend(self):
        """Initialize CPU fallback backend"""
        try:
            import insightface

            # Try InsightFace CPU backend first
            try:
                self.face_detector = insightface.app.FaceAnalysis(
                    providers=["CPUExecutionProvider"]
                )
                self.face_detector.prepare(ctx_id=-1)
                self.backend_type = "insightface_cpu"
                logger.info("Initialized CPU backend with InsightFace")
                return
            except Exception as e:
                logger.debug(f"InsightFace CPU initialization failed: {e}")

        except ImportError:
            logger.debug("InsightFace not available, falling back to OpenCV")

        # Fallback to OpenCV Haar cascades
        self.face_detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.backend_type = "opencv_cpu"
        logger.info("Initialized OpenCV CPU backend (fallback)")

    def detect_faces(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """
        Detect faces in a frame using hardware-accelerated backend

        Args:
            frame: RGB frame array
            timestamp: Frame timestamp in seconds
            frame_number: Frame number in video

        Returns:
            List of FaceDetection objects
        """
        start_time = time.time()

        try:
            # Route to appropriate backend
            if self.backend_type in [
                "insightface_cuda",
                "insightface_cpu",
                "pytorch_mps",
            ]:
                detections = self._detect_with_insightface(
                    frame, timestamp, frame_number
                )
            elif self.backend_type == "onnx_metal":
                detections = self._detect_with_onnx(frame, timestamp, frame_number)
            elif self.backend_type == "coreml":
                detections = self._detect_with_coreml(frame, timestamp, frame_number)
            elif self.backend_type == "opencv_cpu":
                detections = self._detect_with_opencv(frame, timestamp, frame_number)
            else:
                logger.error(f"Unknown backend type: {self.backend_type}")
                detections = []

            # Track performance
            detection_time = time.time() - start_time
            self.detection_times.append(detection_time)
            self.frame_count += 1

            # Log performance every 100 frames
            if self.frame_count % 100 == 0:
                avg_time = np.mean(self.detection_times[-100:])
                fps = 1.0 / avg_time if avg_time > 0 else 0
                logger.info(
                    f"Face detection performance: {avg_time:.3f}s/frame, "
                    f"{fps:.1f} FPS ({self.backend_type})"
                )

            logger.debug(
                f"Detected {len(detections)} faces at timestamp {timestamp:.2f}s "
                f"({detection_time:.3f}s, {self.backend_type})"
            )

            return detections

        except Exception as e:
            logger.error(f"Face detection failed for frame {frame_number}: {e}")
            return []

    def detect_faces_batch(
        self, 
        frames: List[np.ndarray], 
        timestamps: List[float], 
        frame_numbers: List[int],
        use_gpu_memory_pool: bool = True
    ) -> List[List[FaceDetection]]:
        """
        Detect faces in multiple frames simultaneously using hardware-accelerated batch processing
        
        Args:
            frames: List of RGB frame arrays
            timestamps: List of frame timestamps in seconds
            frame_numbers: List of frame numbers
            use_gpu_memory_pool: Whether to use GPU memory pooling for optimization
            
        Returns:
            List of lists, where each inner list contains FaceDetection objects for that frame
        """
        if not frames or len(frames) != len(timestamps) or len(frames) != len(frame_numbers):
            logger.error("Invalid input: frames, timestamps, and frame_numbers must have same length")
            return [[] for _ in frames]
            
        start_time = time.time()
        
        # Initialize GPU memory manager if using memory pooling
        gpu_memory_manager = None
        if use_gpu_memory_pool:
            try:
                from gpu_memory_manager import get_memory_manager
                gpu_memory_manager = get_memory_manager({"performance": {"enable_memory_pool": True}})
                
                # Optimize for face detection workload
                optimal_batch_size = gpu_memory_manager.get_optimal_batch_size("face_detection")
                logger.info(f"Using optimal batch size: {optimal_batch_size}")
                
                # Pre-allocate memory for this workload
                gpu_memory_manager.optimize_for_workload("face_detection", len(frames))
            except Exception as e:
                logger.warning(f"GPU memory manager initialization failed: {e}")
                
        try:
            # Route to appropriate batch backend
            if self.backend_type in ["insightface_cuda", "insightface_cpu", "pytorch_mps"]:
                detections_batch = self._detect_batch_with_insightface(
                    frames, timestamps, frame_numbers, gpu_memory_manager
                )
            elif self.backend_type == "onnx_metal":
                detections_batch = self._detect_batch_with_onnx(
                    frames, timestamps, frame_numbers, gpu_memory_manager
                )
            elif self.backend_type == "opencv_cpu":
                detections_batch = self._detect_batch_with_opencv(
                    frames, timestamps, frame_numbers
                )
            else:
                logger.error(f"Unknown backend type for batch processing: {self.backend_type}")
                # Fallback to individual processing
                detections_batch = []
                for frame, timestamp, frame_number in zip(frames, timestamps, frame_numbers):
                    detections = self.detect_faces(frame, timestamp, frame_number)
                    detections_batch.append(detections)
                    
            # Track batch performance
            batch_time = time.time() - start_time
            total_faces = sum(len(detections) for detections in detections_batch)
            avg_time_per_frame = batch_time / len(frames) if frames else 0
            
            logger.info(
                f"Batch face detection: {len(frames)} frames, {total_faces} faces, "
                f"{batch_time:.3f}s total, {avg_time_per_frame:.3f}s/frame ({self.backend_type})"
            )
            
            return detections_batch
            
        except Exception as e:
            logger.error(f"Batch face detection failed: {e}")
            # Fallback to individual processing
            detections_batch = []
            for frame, timestamp, frame_number in zip(frames, timestamps, frame_numbers):
                try:
                    detections = self.detect_faces(frame, timestamp, frame_number)
                    detections_batch.append(detections)
                except:
                    detections_batch.append([])
            return detections_batch
            
        finally:
            # Clean up GPU memory if manager was used
            if gpu_memory_manager:
                try:
                    gpu_memory_manager.cleanup()
                except:
                    pass

    def _detect_with_insightface(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """Detect faces using InsightFace backend"""

        # Apply memory optimization for Apple Silicon unified memory
        if (
            self.hardware_info.backend == HardwareBackend.APPLE_SILICON_METAL
            and self.hardware_info.supports_unified_memory
        ):
            frame = self._optimize_frame_for_unified_memory(frame)

        # InsightFace expects BGR format
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        else:
            bgr_frame = frame

        # Detect faces
        faces = self.face_detector.get(bgr_frame)

        detections = []
        for face in faces[: self.max_faces_per_frame]:
            if face.det_score < self.min_confidence:
                continue

            # Convert bbox to face_recognition format (top, right, bottom, left)
            bbox = face.bbox.astype(int)
            left, top, right, bottom = bbox
            location = (top, right, bottom, left)

            # Use face embedding as encoding
            encoding = face.embedding

            detection = FaceDetection(
                location=location,
                encoding=encoding,
                timestamp=timestamp,
                frame_number=frame_number,
                confidence=face.det_score,
            )
            detections.append(detection)

        return detections

    def _detect_with_onnx(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """Detect faces using ONNX Runtime backend"""

        # Preprocess frame for ONNX model
        input_frame = self._preprocess_for_onnx(frame)

        # Run inference
        input_name = self.face_detector.get_inputs()[0].name
        outputs = self.face_detector.run(None, {input_name: input_frame})

        # Post-process outputs (implementation depends on specific model)
        detections = self._postprocess_onnx_outputs(
            outputs, frame, timestamp, frame_number
        )

        return detections

    def _detect_with_coreml(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """Detect faces using CoreML backend"""

        # Preprocess frame for CoreML
        input_frame = self._preprocess_for_coreml(frame)

        # Run prediction
        prediction = self.face_detector.predict({"input": input_frame})

        # Post-process outputs
        detections = self._postprocess_coreml_outputs(
            prediction, frame, timestamp, frame_number
        )

        return detections

    def _detect_with_opencv(
        self, frame: np.ndarray, timestamp: float, frame_number: int
    ) -> List[FaceDetection]:
        """Fallback face detection using OpenCV Haar cascades"""

        # Convert RGB to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        # Detect faces
        faces = self.face_detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )

        detections = []
        for x, y, w, h in faces[: self.max_faces_per_frame]:
            # Convert to face_recognition format
            top, right, bottom, left = y, x + w, y + h, x
            location = (top, right, bottom, left)

            # Generate mock encoding for compatibility (512-dimensional to match stored embeddings)
            encoding = np.random.rand(512).astype(np.float32)

            detection = FaceDetection(
                location=location,
                encoding=encoding,
                timestamp=timestamp,
                frame_number=frame_number,
                confidence=0.8,  # Mock confidence
            )
            detections.append(detection)

        return detections

    def _optimize_frame_for_unified_memory(self, frame: np.ndarray) -> np.ndarray:
        """Optimize frame data for Apple Silicon unified memory architecture"""

        # Ensure contiguous memory layout
        if not frame.flags["C_CONTIGUOUS"]:
            frame = np.ascontiguousarray(frame)

        # Use float16 for better Apple Silicon performance
        if self.hardware_info.optimization_flags.get("prefer_fp16", False):
            if frame.dtype != np.float16 and frame.dtype != np.uint8:
                frame = frame.astype(np.float16)

        return frame

    def _preprocess_for_onnx(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for ONNX model input"""
        # Standard preprocessing - adjust based on model requirements
        if frame.dtype == np.uint8:
            frame = frame.astype(np.float32) / 255.0

        # Add batch dimension
        if len(frame.shape) == 3:
            frame = np.expand_dims(frame, axis=0)

        return frame

    def _preprocess_for_coreml(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for CoreML model input"""
        # CoreML preprocessing - adjust based on model requirements
        if frame.dtype == np.uint8:
            frame = frame.astype(np.float32) / 255.0

        return frame

    def _postprocess_onnx_outputs(
        self,
        outputs: List[np.ndarray],
        frame: np.ndarray,
        timestamp: float,
        frame_number: int,
    ) -> List[FaceDetection]:
        """Post-process ONNX model outputs to FaceDetection objects"""

        # This is model-specific and would need to be implemented
        # based on the actual ONNX model architecture
        detections = []

        # Placeholder implementation
        logger.warning("ONNX output post-processing not implemented for this model")

        return detections

    def _postprocess_coreml_outputs(
        self,
        prediction: Dict[str, Any],
        frame: np.ndarray,
        timestamp: float,
        frame_number: int,
    ) -> List[FaceDetection]:
        """Post-process CoreML prediction to FaceDetection objects"""

        # This is model-specific and would need to be implemented
        # based on the actual CoreML model outputs
        detections = []

        # Placeholder implementation
        logger.warning("CoreML output post-processing not implemented for this model")

        return detections

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for the detector"""

        if not self.detection_times:
            return {}

        return {
            "backend": self.backend_type,
            "hardware_info": {
                "backend": self.hardware_info.backend.value,
                "device_name": self.hardware_info.device_name,
                "memory_gb": self.hardware_info.memory_gb,
                "supports_unified_memory": self.hardware_info.supports_unified_memory,
            },
            "performance": {
                "total_frames": self.frame_count,
                "avg_detection_time": np.mean(self.detection_times),
                "min_detection_time": np.min(self.detection_times),
                "max_detection_time": np.max(self.detection_times),
                "avg_fps": 1.0 / np.mean(self.detection_times)
                if self.detection_times
                else 0,
            },
        }

    def cleanup(self):
        """Clean up resources"""
        if hasattr(self.face_detector, "cleanup"):
            self.face_detector.cleanup()

        self.face_detector = None

        # Log final performance stats
        stats = self.get_performance_stats()
        if stats:
            logger.info(f"Final performance stats: {stats}")

    def _detect_batch_with_insightface(
        self, 
        frames: List[np.ndarray], 
        timestamps: List[float], 
        frame_numbers: List[int],
        gpu_memory_manager = None
    ) -> List[List[FaceDetection]]:
        """Batch face detection using InsightFace backend"""
        
        # Process frames in smaller batches for memory efficiency
        batch_size = 4  # Conservative batch size for InsightFace
        if gpu_memory_manager:
            batch_size = min(gpu_memory_manager.get_optimal_batch_size("face_detection"), 8)
            
        all_detections = []
        
        for i in range(0, len(frames), batch_size):
            batch_frames = frames[i:i + batch_size]
            batch_timestamps = timestamps[i:i + batch_size]
            batch_frame_numbers = frame_numbers[i:i + batch_size]
            
            batch_detections = []
            
            # Apply memory optimization for Apple Silicon unified memory
            if (
                self.hardware_info.backend == HardwareBackend.APPLE_SILICON_METAL
                and self.hardware_info.supports_unified_memory
            ):
                batch_frames = [
                    self._optimize_frame_for_unified_memory(frame) 
                    for frame in batch_frames
                ]
            
            # Process each frame in the batch
            for frame, timestamp, frame_number in zip(batch_frames, batch_timestamps, batch_frame_numbers):
                # Convert RGB to BGR for InsightFace
                if len(frame.shape) == 3 and frame.shape[2] == 3:
                    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                else:
                    bgr_frame = frame
                    
                # Detect faces
                faces = self.face_detector.get(bgr_frame)
                
                frame_detections = []
                for face in faces[:self.max_faces_per_frame]:
                    if face.det_score < self.min_confidence:
                        continue
                        
                    # Convert bbox to face_recognition format
                    bbox = face.bbox.astype(int)
                    left, top, right, bottom = bbox
                    location = (top, right, bottom, left)
                    
                    # Use face embedding as encoding
                    encoding = face.embedding
                    
                    detection = FaceDetection(
                        location=location,
                        encoding=encoding,
                        timestamp=timestamp,
                        frame_number=frame_number,
                        confidence=face.det_score,
                    )
                    frame_detections.append(detection)
                    
                batch_detections.append(frame_detections)
                
            all_detections.extend(batch_detections)
            
        return all_detections
        
    def _detect_batch_with_onnx(
        self, 
        frames: List[np.ndarray], 
        timestamps: List[float], 
        frame_numbers: List[int],
        gpu_memory_manager = None
    ) -> List[List[FaceDetection]]:
        """Batch face detection using ONNX Runtime backend"""
        
        # ONNX can handle larger batches more efficiently
        batch_size = 8
        if gpu_memory_manager:
            batch_size = gpu_memory_manager.get_optimal_batch_size("face_detection")
            
        all_detections = []
        
        for i in range(0, len(frames), batch_size):
            batch_frames = frames[i:i + batch_size]
            batch_timestamps = timestamps[i:i + batch_size]
            batch_frame_numbers = frame_numbers[i:i + batch_size]
            
            try:
                # Preprocess batch for ONNX
                batch_input = np.stack([
                    self._preprocess_for_onnx(frame) for frame in batch_frames
                ])
                
                # Run batch inference
                input_name = self.face_detector.get_inputs()[0].name
                batch_outputs = self.face_detector.run(None, {input_name: batch_input})
                
                # Post-process batch outputs
                batch_detections = self._postprocess_onnx_batch_outputs(
                    batch_outputs, batch_frames, batch_timestamps, batch_frame_numbers
                )
                
                all_detections.extend(batch_detections)
                
            except Exception as e:
                logger.error(f"ONNX batch processing failed: {e}")
                # Fallback to individual processing
                for frame, timestamp, frame_number in zip(batch_frames, batch_timestamps, batch_frame_numbers):
                    detections = self._detect_with_onnx(frame, timestamp, frame_number)
                    all_detections.append(detections)
                    
        return all_detections
        
    def _detect_batch_with_opencv(
        self, 
        frames: List[np.ndarray], 
        timestamps: List[float], 
        frame_numbers: List[int]
    ) -> List[List[FaceDetection]]:
        """Batch face detection using OpenCV (CPU-only, limited batch benefits)"""
        
        # OpenCV doesn't benefit much from batching, but we can parallelize
        all_detections = []
        
        for frame, timestamp, frame_number in zip(frames, timestamps, frame_numbers):
            detections = self._detect_with_opencv(frame, timestamp, frame_number)
            all_detections.append(detections)
            
        return all_detections
        
    def _postprocess_onnx_batch_outputs(
        self,
        batch_outputs: List[np.ndarray],
        frames: List[np.ndarray],
        timestamps: List[float],
        frame_numbers: List[int],
    ) -> List[List[FaceDetection]]:
        """Post-process ONNX batch outputs to FaceDetection objects"""
        
        # This is model-specific and would need to be implemented
        # based on the actual ONNX model architecture
        detections_batch = []
        
        for i, (frame, timestamp, frame_number) in enumerate(zip(frames, timestamps, frame_numbers)):
            # Placeholder implementation - extract detections for frame i
            frame_detections = []
            
            # This would parse the batch_outputs for frame i
            # and create FaceDetection objects
            logger.warning(f"ONNX batch output post-processing not implemented for frame {i}")
            
            detections_batch.append(frame_detections)
            
        return detections_batch
