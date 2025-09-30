import pytest
import json
import tempfile
from pathlib import Path

from src.segmentation_metrics import SegmentationMetrics


class TestSegmentationMetrics:
    def test_metrics_initialization(self):
        metrics = SegmentationMetrics(video_id="test_video")
        
        assert metrics.video_id == "test_video"
        assert metrics.total_frames == 0
        assert metrics.segmentation_runs == 0
        assert metrics.cache_hits == 0
    
    def test_record_segmentation(self):
        metrics = SegmentationMetrics(video_id="test_video")
        
        metrics.record_segmentation(num_rois=3)
        metrics.record_segmentation(num_rois=2)
        
        assert metrics.segmentation_runs == 2
        assert metrics.total_rois == 5
    
    def test_record_cache_operations(self):
        metrics = SegmentationMetrics(video_id="test_video")
        
        metrics.record_cache_hit()
        metrics.record_cache_hit()
        metrics.record_cache_miss()
        
        assert metrics.cache_hits == 2
        assert metrics.cache_misses == 1
    
    def test_record_face_validation(self):
        metrics = SegmentationMetrics(video_id="test_video")
        
        metrics.record_face_validation(validated=8, rejected=2)
        
        assert metrics.faces_parsed == 10
        assert metrics.faces_rejected == 2
    
    def test_get_summary_with_data(self):
        metrics = SegmentationMetrics(video_id="test_video")
        metrics.total_frames = 100
        metrics.record_segmentation(3)
        metrics.record_segmentation(2)
        metrics.record_cache_hit()
        metrics.record_cache_hit()
        metrics.record_cache_miss()
        metrics.record_faces_detected(10)
        metrics.record_face_validation(validated=8, rejected=2)
        metrics.set_processing_time(5.0)
        metrics.set_baseline_time(10.0)
        
        summary = metrics.get_summary()
        
        assert summary["video_id"] == "test_video"
        assert summary["total_frames"] == 100
        assert summary["segmentation_runs"] == 2
        assert summary["roi_count_avg"] == 2.5
        assert summary["cache_hit_rate"] == pytest.approx(0.667, abs=0.01)
        assert summary["faces_detected"] == 10
        assert summary["faces_parsed"] == 10
        assert summary["faces_rejected"] == 2
        assert summary["parsing_rejection_rate"] == 0.2
        assert summary["processing_time_seconds"] == 5.0
        assert summary["speedup_vs_baseline_pct"] == 50.0
    
    def test_export_and_load_json(self):
        metrics = SegmentationMetrics(video_id="test_video")
        metrics.total_frames = 100
        metrics.record_segmentation(3)
        metrics.record_cache_hit()
        metrics.set_processing_time(5.0)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            metrics.export_json(temp_path)
            
            assert Path(temp_path).exists()
            
            with open(temp_path, 'r') as f:
                data = json.load(f)
            
            assert data["video_id"] == "test_video"
            assert data["total_frames"] == 100
            assert data["segmentation_runs"] == 1
            
            loaded_metrics = SegmentationMetrics.load_from_json(temp_path)
            assert loaded_metrics.video_id == "test_video"
            assert loaded_metrics.total_frames == 100
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_zero_division_safety(self):
        metrics = SegmentationMetrics(video_id="test_video")
        
        summary = metrics.get_summary()
        
        assert summary["roi_count_avg"] == 0.0
        assert summary["cache_hit_rate"] == 0.0
        assert summary["parsing_rejection_rate"] == 0.0
        assert summary["speedup_vs_baseline_pct"] == 0.0
