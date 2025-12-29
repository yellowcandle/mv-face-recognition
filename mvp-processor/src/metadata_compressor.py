"""
Metadata Compression Module
Reduces metadata file size through delta encoding and compression
"""

import json
import gzip
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeltaFrame:
    """Frame data using delta encoding"""
    frame_number: int
    timestamp: Optional[float] = None  # Only if changed
    faces: Optional[List[Dict[str, Any]]] = None  # Only if new/updated
    action: str = "continue"  # "continue", "update", "full"


class MetadataCompressor:
    """Compresses metadata using delta encoding and gzip"""
    
    @staticmethod
    def compress_dense_metadata(
        metadata: Dict[str, Any],
        compression_level: int = 9
    ) -> bytes:
        """
        Compress dense metadata to bytes
        
        Args:
            metadata: Full metadata dictionary
            compression_level: gzip compression (1-9)
            
        Returns:
            Compressed metadata bytes
        """
        json_str = json.dumps(metadata, separators=(',', ':'))
        return gzip.compress(json_str.encode('utf-8'), compresslevel=compression_level)
    
    @staticmethod
    def decompress_dense_metadata(data: bytes) -> Dict[str, Any]:
        """Decompress dense metadata"""
        json_str = gzip.decompress(data).decode('utf-8')
        return json.loads(json_str)
    
    @staticmethod
    def encode_delta_metadata(
        frames: List[Dict[str, Any]]
    ) -> List[DeltaFrame]:
        """
        Encode frames using delta encoding
        
        Reduces size by:
        - Only storing changed values
        - Using relative references
        - Omitting duplicate face detections
        
        Args:
            frames: List of frame metadata dicts
            
        Returns:
            List of delta-encoded frames
        """
        delta_frames = []
        prev_timestamp = None
        prev_faces = {}
        
        for frame_data in frames:
            frame_num = frame_data.get('frame_number')
            timestamp = frame_data.get('timestamp')
            faces = frame_data.get('faces', [])
            
            delta = DeltaFrame(frame_number=frame_num)
            
            # Store timestamp only if changed
            if timestamp != prev_timestamp:
                delta.timestamp = timestamp
                prev_timestamp = timestamp
            
            # Process faces with delta encoding
            if faces:
                delta_faces = []
                for face in faces:
                    face_id = face.get('id')
                    
                    # Check if face is new or changed
                    prev_face = prev_faces.get(face_id)
                    if prev_face != face:
                        delta_faces.append(face)
                        prev_faces[face_id] = face
                
                if delta_faces:
                    delta.faces = delta_faces
                    delta.action = "update"
                else:
                    delta.action = "continue"
            else:
                delta.action = "continue"
            
            delta_frames.append(delta)
        
        return delta_frames
    
    @staticmethod
    def decode_delta_metadata(delta_frames: List[DeltaFrame]) -> List[Dict[str, Any]]:
        """
        Decode delta-encoded frames back to full metadata
        
        Args:
            delta_frames: List of delta-encoded frames
            
        Returns:
            List of full frame metadata dicts
        """
        frames = []
        current_timestamp = None
        current_faces = {}
        
        for delta in delta_frames:
            frame_data = {'frame_number': delta.frame_number}
            
            # Restore timestamp
            if delta.timestamp is not None:
                current_timestamp = delta.timestamp
            frame_data['timestamp'] = current_timestamp
            
            # Restore faces
            if delta.faces:
                for face in delta.faces:
                    face_id = face.get('id')
                    current_faces[face_id] = face
            
            frame_data['faces'] = list(current_faces.values())
            frames.append(frame_data)
        
        return frames
    
    @staticmethod
    def calculate_compression_stats(
        original_data: Dict[str, Any],
        compressed_data: bytes
    ) -> Dict[str, Any]:
        """
        Calculate compression statistics
        
        Args:
            original_data: Original metadata dict
            compressed_data: Compressed bytes
            
        Returns:
            Statistics dict
        """
        original_json = json.dumps(original_data, separators=(',', ':')).encode('utf-8')
        original_size = len(original_json)
        compressed_size = len(compressed_data)
        compression_ratio = original_size / compressed_size if compressed_size > 0 else 0
        
        return {
            'original_bytes': original_size,
            'compressed_bytes': compressed_size,
            'compression_ratio': f"{compression_ratio:.2f}x",
            'reduction_percentage': f"{(1 - compressed_size/original_size)*100:.1f}%",
            'estimated_kb_original': original_size / 1024,
            'estimated_kb_compressed': compressed_size / 1024,
        }


class MetadataOptimizer:
    """Optimizes metadata structure for smaller file sizes"""
    
    @staticmethod
    def optimize_frame_metadata(
        frame_data: Dict[str, Any],
        prune_low_confidence: float = 0.1
    ) -> Dict[str, Any]:
        """
        Optimize frame metadata
        
        Args:
            frame_data: Frame metadata dict
            prune_low_confidence: Remove faces below this confidence
            
        Returns:
            Optimized metadata dict
        """
        optimized = {
            'f': frame_data.get('frame_number'),  # Abbreviate keys
            't': frame_data.get('timestamp'),
        }
        
        faces = frame_data.get('faces', [])
        if faces:
            # Filter low confidence
            faces = [
                f for f in faces 
                if f.get('confidence', 1.0) >= prune_low_confidence
            ]
            
            # Abbreviate face data
            optimized['fs'] = [
                {
                    'id': f.get('id'),
                    'c': f.get('contestant_id'),
                    'n': f.get('name'),
                    'x': f.get('bbox', {}).get('x'),
                    'y': f.get('bbox', {}).get('y'),
                    'w': f.get('bbox', {}).get('width'),
                    'h': f.get('bbox', {}).get('height'),
                    'conf': f.get('confidence'),
                }
                for f in faces
            ]
        
        return optimized
    
    @staticmethod
    def unoptimize_frame_metadata(optimized: Dict[str, Any]) -> Dict[str, Any]:
        """Restore optimized metadata to full format"""
        return {
            'frame_number': optimized.get('f'),
            'timestamp': optimized.get('t'),
            'faces': [
                {
                    'id': f.get('id'),
                    'contestant_id': f.get('c'),
                    'name': f.get('n'),
                    'bbox': {
                        'x': f.get('x'),
                        'y': f.get('y'),
                        'width': f.get('w'),
                        'height': f.get('h'),
                    },
                    'confidence': f.get('conf'),
                }
                for f in optimized.get('fs', [])
            ]
        }
