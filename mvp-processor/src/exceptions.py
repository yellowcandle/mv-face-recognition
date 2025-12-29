"""
Custom Exception Hierarchy for Face Recognition System

Provides structured exceptions with context for:
- Video processing errors
- Face detection/recognition errors
- Storage/database errors
- Upload errors
"""

from typing import Optional, Any, Dict
import traceback


class FaceRecognitionError(Exception):
    """Base exception for all face recognition system errors."""

    def __init__(
        self,
        message: str,
        code: str = "FACE_RECOGNITION_ERROR",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        """Serialize exception for API responses or logging."""
        result = {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }
        if self.cause:
            result["error"]["cause"] = str(self.cause)
        return result

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


# =============================================================================
# Video Processing Errors
# =============================================================================


class VideoProcessingError(FaceRecognitionError):
    """Base exception for video processing failures."""

    def __init__(
        self,
        message: str,
        video_path: Optional[str] = None,
        cause: Optional[Exception] = None,
        **details,
    ):
        super().__init__(
            message,
            code="VIDEO_PROCESSING_ERROR",
            details={"video_path": video_path, **details},
            cause=cause,
        )
        self.video_path = video_path


class VideoNotFoundError(VideoProcessingError):
    """Raised when video file does not exist."""

    def __init__(self, video_path: str):
        super().__init__(
            f"Video file not found: {video_path}",
            video_path=video_path,
        )
        self.code = "VIDEO_NOT_FOUND"


class CorruptedVideoError(VideoProcessingError):
    """Raised when video file is corrupted or unreadable."""

    def __init__(
        self,
        message: str,
        video_path: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message, video_path=video_path, cause=cause)
        self.code = "CORRUPTED_VIDEO"


class UnsupportedFormatError(VideoProcessingError):
    """Raised when video format is not supported."""

    def __init__(self, video_path: str, detected_format: Optional[str] = None):
        super().__init__(
            f"Unsupported video format: {detected_format or 'unknown'}",
            video_path=video_path,
            detected_format=detected_format,
        )
        self.code = "UNSUPPORTED_FORMAT"
        self.detected_format = detected_format


class FrameExtractionError(VideoProcessingError):
    """Raised when frame extraction fails."""

    def __init__(
        self,
        message: str,
        video_path: Optional[str] = None,
        frame_number: Optional[int] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            video_path=video_path,
            frame_number=frame_number,
            cause=cause,
        )
        self.code = "FRAME_EXTRACTION_ERROR"
        self.frame_number = frame_number


# =============================================================================
# Face Detection/Recognition Errors
# =============================================================================


class FaceDetectionError(FaceRecognitionError):
    """Raised when face detection fails."""

    def __init__(
        self,
        message: str,
        frame_number: Optional[int] = None,
        cause: Optional[Exception] = None,
        **details,
    ):
        super().__init__(
            message,
            code="FACE_DETECTION_ERROR",
            details={"frame_number": frame_number, **details},
            cause=cause,
        )
        self.frame_number = frame_number


class ModelLoadError(FaceDetectionError):
    """Raised when face detection model fails to load."""

    def __init__(self, model_path: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Failed to load model: {model_path}",
            cause=cause,
            model_path=model_path,
        )
        self.code = "MODEL_LOAD_ERROR"
        self.model_path = model_path


class EmbeddingGenerationError(FaceRecognitionError):
    """Raised when face embedding generation fails."""

    def __init__(
        self,
        message: str,
        contestant_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            code="EMBEDDING_GENERATION_ERROR",
            details={"contestant_id": contestant_id},
            cause=cause,
        )
        self.contestant_id = contestant_id


class RecognitionMatchError(FaceRecognitionError):
    """Raised when recognition matching fails."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(
            message,
            code="RECOGNITION_MATCH_ERROR",
            cause=cause,
        )


# =============================================================================
# Database Errors
# =============================================================================


class DatabaseError(FaceRecognitionError):
    """Base exception for database operation failures."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        cause: Optional[Exception] = None,
        **details,
    ):
        super().__init__(
            message,
            code="DATABASE_ERROR",
            details={"operation": operation, **details},
            cause=cause,
        )
        self.operation = operation


class ChromaDBError(DatabaseError):
    """Raised when ChromaDB operations fail."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        collection: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            operation=operation,
            collection=collection,
            cause=cause,
        )
        self.code = "CHROMADB_ERROR"
        self.collection = collection


class EmbeddingNotFoundError(DatabaseError):
    """Raised when required embedding is not found in database."""

    def __init__(self, contestant_id: str):
        super().__init__(
            f"Embedding not found for contestant: {contestant_id}",
            operation="query",
            contestant_id=contestant_id,
        )
        self.code = "EMBEDDING_NOT_FOUND"
        self.contestant_id = contestant_id


# =============================================================================
# Upload/Storage Errors
# =============================================================================


class UploadError(FaceRecognitionError):
    """Base exception for upload failures."""

    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        resource: Optional[str] = None,
        cause: Optional[Exception] = None,
        **details,
    ):
        super().__init__(
            message,
            code="UPLOAD_ERROR",
            details={"service": service, "resource": resource, **details},
            cause=cause,
        )
        self.service = service
        self.resource = resource


class CloudflareUploadError(UploadError):
    """Raised when Cloudflare upload fails."""

    def __init__(
        self,
        message: str,
        bucket: Optional[str] = None,
        key: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message,
            service="cloudflare_r2",
            resource=key,
            bucket=bucket,
            cause=cause,
        )
        self.code = "CLOUDFLARE_UPLOAD_ERROR"
        self.bucket = bucket
        self.key = key


class CloudflareAuthError(UploadError):
    """Raised when Cloudflare authentication fails."""

    def __init__(self, message: str = "Cloudflare authentication failed"):
        super().__init__(message, service="cloudflare")
        self.code = "CLOUDFLARE_AUTH_ERROR"


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(FaceRecognitionError):
    """Raised when configuration is invalid or missing."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        expected_type: Optional[str] = None,
    ):
        super().__init__(
            message,
            code="CONFIGURATION_ERROR",
            details={"config_key": config_key, "expected_type": expected_type},
        )
        self.config_key = config_key


class MissingConfigError(ConfigurationError):
    """Raised when required configuration is missing."""

    def __init__(self, config_key: str):
        super().__init__(f"Missing required configuration: {config_key}", config_key=config_key)
        self.code = "MISSING_CONFIG"


# =============================================================================
# Utility Functions
# =============================================================================


def format_exception_chain(error: Exception, include_traceback: bool = False) -> str:
    """Format an exception and its cause chain as a readable string."""
    messages = []
    current = error

    while current is not None:
        if isinstance(current, FaceRecognitionError):
            messages.append(f"[{current.code}] {current.message}")
        else:
            messages.append(f"[{type(current).__name__}] {str(current)}")

        if hasattr(current, "cause"):
            current = current.cause
        elif hasattr(current, "__cause__"):
            current = current.__cause__
        else:
            break

    result = " -> ".join(messages)

    if include_traceback:
        result += f"\n\nTraceback:\n{traceback.format_exc()}"

    return result


def wrap_exception(
    error: Exception,
    wrapper_class: type,
    message: Optional[str] = None,
    **kwargs,
) -> FaceRecognitionError:
    """Wrap a generic exception in a FaceRecognitionError subclass."""
    if isinstance(error, FaceRecognitionError):
        return error

    msg = message or str(error)
    return wrapper_class(msg, cause=error, **kwargs)
