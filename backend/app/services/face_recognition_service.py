"""
Main face recognition service that integrates all components.
"""

import asyncio
import logging
from typing import Dict, Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """Main service that coordinates all face recognition functionality."""
    
    def __init__(self):
        """Initialize the face recognition service."""
        self.settings = get_settings()
        self.initialized = False
        
        # Core components (will be initialized later)
        self.face_detector = None
        self.face_matcher = None
        self.video_processor = None
        self.chroma_manager = None
    
    async def initialize(self):
        """Initialize all components."""
        if self.initialized:
            return
        
        try:
            logger.info("Initializing face recognition service...")
            
            # Import here to avoid circular imports
            import sys
            sys.path.append('../src')
            
            from src.core.face_detector import FaceDetector
            from src.core.face_matcher import FaceMatcher
            from src.services.video_processor import VideoProcessor
            from src.database.chroma_setup import ChromaDBManager
            
            # Initialize components
            config_path = self.settings.config_file
            
            self.face_detector = FaceDetector(config_path)
            self.face_matcher = FaceMatcher(config_path)
            self.video_processor = VideoProcessor(config_path)
            self.chroma_manager = ChromaDBManager()
            
            # Verify ChromaDB connection
            await self._verify_chroma_connection()
            
            self.initialized = True
            logger.info("Face recognition service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize face recognition service: {e}")
            raise
    
    async def _verify_chroma_connection(self):
        """Verify ChromaDB connection and data."""
        try:
            # Test ChromaDB connection
            collection = self.chroma_manager.get_collection()
            count = collection.count()
            logger.info(f"ChromaDB connected successfully. {count} embeddings available.")
            
        except Exception as e:
            logger.warning(f"ChromaDB connection issue: {e}")
            # Don't fail initialization - can work without ChromaDB
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all components."""
        if not self.initialized:
            return {
                "status": "error",
                "message": "Service not initialized",
                "services": {
                    "face_detector": False,
                    "face_matcher": False,
                    "video_processor": False,
                    "chromadb": False
                }
            }
        
        services = {}
        
        # Check face detector
        try:
            services["face_detector"] = self.face_detector.app is not None
        except:
            services["face_detector"] = False
        
        # Check face matcher
        try:
            services["face_matcher"] = self.face_matcher.collection is not None
        except:
            services["face_matcher"] = False
        
        # Check video processor
        try:
            services["video_processor"] = self.video_processor is not None
        except:
            services["video_processor"] = False
        
        # Check ChromaDB
        try:
            collection = self.chroma_manager.get_collection()
            services["chromadb"] = collection.count() > 0
        except:
            services["chromadb"] = False
        
        all_healthy = all(services.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": str(asyncio.get_event_loop().time()),
            "services": services,
            "version": "1.0.0"
        }
    
    async def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up face recognition service...")
        
        # Cleanup components if needed
        if self.chroma_manager:
            try:
                # Close any connections
                pass
            except Exception as e:
                logger.warning(f"Error during ChromaDB cleanup: {e}")
        
        self.initialized = False
        logger.info("Face recognition service cleanup complete")
    
    def get_face_detector(self):
        """Get face detector instance."""
        if not self.initialized:
            raise RuntimeError("Service not initialized")
        return self.face_detector
    
    def get_face_matcher(self):
        """Get face matcher instance."""
        if not self.initialized:
            raise RuntimeError("Service not initialized")
        return self.face_matcher
    
    def get_video_processor(self):
        """Get video processor instance."""
        if not self.initialized:
            raise RuntimeError("Service not initialized")
        return self.video_processor
    
    def get_chroma_manager(self):
        """Get ChromaDB manager instance."""
        if not self.initialized:
            raise RuntimeError("Service not initialized")
        return self.chroma_manager