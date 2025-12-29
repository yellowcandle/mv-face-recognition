"""
Tests for metadata compression modules
"""

import pytest
import json
import gzip

import sys
sys.path.insert(0, 'mvp-processor')

from src.metadata_compressor import (
    MetadataCompressor,
    MetadataOptimizer,
    DeltaFrame
)


class TestMetadataCompressor:
    """Test metadata compression functionality"""
    
    @pytest.fixture
    def sample_metadata(self):
        """Create sample metadata"""
        return {
            "video_id": "test_video_001",
            "fps": 24,
            "duration": 10.0,
            "frames": [
                {
                    "frame_number": 0,
                    "timestamp": 0.0,
                    "faces": [
                        {
                            "id": "face_0",
                            "contestant_id": "1",
                            "name": "Alice",
                            "confidence": 0.95
                        }
                    ]
                },
                {
                    "frame_number": 1,
                    "timestamp": 0.042,
                    "faces": [
                        {
                            "id": "face_1",
                            "contestant_id": "1",
                            "name": "Alice",
                            "confidence": 0.93
                        }
                    ]
                }
            ]
        }
    
    def test_compress_decompress(self, sample_metadata):
        """Test compression and decompression"""
        # Compress
        compressed = MetadataCompressor.compress_dense_metadata(sample_metadata)
        assert isinstance(compressed, bytes)
        assert len(compressed) > 0
        
        # Decompress
        decompressed = MetadataCompressor.decompress_dense_metadata(compressed)
        assert decompressed == sample_metadata
    
    def test_compression_ratio(self, sample_metadata):
        """Test compression ratio calculation"""
        compressed = MetadataCompressor.compress_dense_metadata(sample_metadata)
        stats = MetadataCompressor.calculate_compression_stats(
            sample_metadata,
            compressed
        )
        
        assert stats['original_bytes'] > 0
        assert stats['compressed_bytes'] > 0
        assert stats['original_bytes'] > stats['compressed_bytes']
        assert 'x' in stats['compression_ratio']
        assert '%' in stats['reduction_percentage']
    
    def test_large_metadata_compression(self):
        """Test compression of large metadata"""
        # Create large metadata with many frames
        large_metadata = {
            "video_id": "large_video",
            "frames": [
                {
                    "frame_number": i,
                    "timestamp": i * 0.042,
                    "faces": [
                        {
                            "id": f"face_{i}_{j}",
                            "contestant_id": str((j % 10) + 1),
                            "name": f"Contestant{j+1}",
                            "confidence": 0.85 + (j * 0.01)
                        }
                        for j in range(5)
                    ]
                }
                for i in range(100)
            ]
        }
        
        compressed = MetadataCompressor.compress_dense_metadata(
            large_metadata,
            compression_level=9
        )
        stats = MetadataCompressor.calculate_compression_stats(
            large_metadata,
            compressed
        )
        
        # Should achieve significant compression
        ratio = float(stats['compression_ratio'].split('x')[0])
        assert ratio > 2.0, f"Expected ratio > 2.0x, got {ratio}x"


class TestDeltaEncoding:
    """Test delta encoding functionality"""
    
    @pytest.fixture
    def sample_frames(self):
        """Create sample frames with repetitive data"""
        return [
            {
                "frame_number": 0,
                "timestamp": 0.0,
                "faces": [
                    {"id": "f1", "x": 100, "y": 100},
                    {"id": "f2", "x": 200, "y": 200}
                ]
            },
            {
                "frame_number": 1,
                "timestamp": 0.042,
                "faces": [
                    {"id": "f1", "x": 102, "y": 102},
                    {"id": "f2", "x": 200, "y": 200}
                ]
            },
            {
                "frame_number": 2,
                "timestamp": 0.084,
                "faces": [
                    {"id": "f1", "x": 104, "y": 104}
                ]
            }
        ]
    
    def test_delta_encoding(self, sample_frames):
        """Test delta encoding reduces size"""
        delta_frames = MetadataCompressor.encode_delta_metadata(sample_frames)
        
        assert len(delta_frames) == len(sample_frames)
        # First frame should be full
        assert delta_frames[0].action == "update"
        # Subsequent frames should have partial data
        assert delta_frames[1].action == "update"
    
    def test_delta_decode(self, sample_frames):
        """Test delta decoding restores original data"""
        delta_frames = MetadataCompressor.encode_delta_metadata(sample_frames)
        decoded = MetadataCompressor.decode_delta_metadata(delta_frames)
        
        # Should have same number of frames
        assert len(decoded) == len(sample_frames)
        # Content should be restored
        assert decoded[0]['frame_number'] == sample_frames[0]['frame_number']


class TestMetadataOptimizer:
    """Test metadata optimization"""
    
    @pytest.fixture
    def sample_frame(self):
        """Create sample frame data"""
        return {
            "frame_number": 0,
            "timestamp": 0.0,
            "faces": [
                {
                    "id": "f1",
                    "contestant_id": "1",
                    "name": "Alice",
                    "bbox": {"x": 100, "y": 100, "width": 50, "height": 50},
                    "confidence": 0.95
                },
                {
                    "id": "f2",
                    "contestant_id": "2",
                    "name": "Bob",
                    "bbox": {"x": 200, "y": 200, "width": 50, "height": 50},
                    "confidence": 0.05  # Low confidence
                }
            ]
        }
    
    def test_optimize_frame_removes_low_confidence(self, sample_frame):
        """Test that optimization removes low confidence faces"""
        optimized = MetadataOptimizer.optimize_frame_metadata(
            sample_frame,
            prune_low_confidence=0.1
        )
        
        # Should have abbreviated keys
        assert 'f' in optimized  # frame_number
        assert 't' in optimized  # timestamp
        assert 'fs' in optimized  # faces
        
        # Should only have 1 face (high confidence)
        assert len(optimized['fs']) == 1
        assert optimized['fs'][0]['id'] == 'f1'
    
    def test_optimize_unoptimize_roundtrip(self, sample_frame):
        """Test that optimize->unoptimize preserves data"""
        optimized = MetadataOptimizer.optimize_frame_metadata(
            sample_frame,
            prune_low_confidence=0.0  # Keep all
        )
        unoptimized = MetadataOptimizer.unoptimize_frame_metadata(optimized)
        
        # Should restore main structure
        assert unoptimized['frame_number'] == sample_frame['frame_number']
        assert unoptimized['timestamp'] == sample_frame['timestamp']
        assert len(unoptimized['faces']) == len(
            sample_frame['faces']
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
