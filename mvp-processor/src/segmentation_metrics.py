import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class SegmentationMetrics:
    video_id: str
    total_frames: int = 0
    segmentation_runs: int = 0
    total_rois: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    faces_detected: int = 0
    faces_parsed: int = 0
    faces_rejected: int = 0
    processing_time_seconds: float = 0.0
    baseline_time_seconds: float = 0.0
    
    def record_segmentation(self, num_rois: int):
        self.segmentation_runs += 1
        self.total_rois += num_rois
    
    def record_cache_hit(self):
        self.cache_hits += 1
    
    def record_cache_miss(self):
        self.cache_misses += 1
    
    def record_faces_detected(self, count: int):
        self.faces_detected += count
    
    def record_face_validation(self, validated: int, rejected: int):
        self.faces_parsed += validated + rejected
        self.faces_rejected += rejected
    
    def set_processing_time(self, seconds: float):
        self.processing_time_seconds = seconds
    
    def set_baseline_time(self, seconds: float):
        self.baseline_time_seconds = seconds
    
    def get_summary(self) -> Dict[str, Any]:
        cache_hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0.0
        roi_count_avg = self.total_rois / self.segmentation_runs if self.segmentation_runs > 0 else 0.0
        parsing_rejection_rate = self.faces_rejected / self.faces_parsed if self.faces_parsed > 0 else 0.0
        speedup_pct = ((self.baseline_time_seconds - self.processing_time_seconds) / self.baseline_time_seconds * 100) if self.baseline_time_seconds > 0 else 0.0
        
        return {
            "video_id": self.video_id,
            "total_frames": self.total_frames,
            "segmentation_runs": self.segmentation_runs,
            "roi_count_avg": round(roi_count_avg, 2),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(cache_hit_rate, 3),
            "faces_detected": self.faces_detected,
            "faces_parsed": self.faces_parsed,
            "faces_rejected": self.faces_rejected,
            "parsing_rejection_rate": round(parsing_rejection_rate, 3),
            "processing_time_seconds": round(self.processing_time_seconds, 2),
            "baseline_time_seconds": round(self.baseline_time_seconds, 2),
            "speedup_vs_baseline_pct": round(speedup_pct, 1)
        }
    
    def export_json(self, output_path: str):
        with open(output_path, 'w') as f:
            json.dump(self.get_summary(), f, indent=2)
    
    @classmethod
    def load_from_json(cls, json_path: str) -> 'SegmentationMetrics':
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        metrics = cls(video_id=data['video_id'])
        metrics.total_frames = data.get('total_frames', 0)
        metrics.segmentation_runs = data.get('segmentation_runs', 0)
        metrics.cache_hits = data.get('cache_hits', 0)
        metrics.cache_misses = data.get('cache_misses', 0)
        metrics.faces_detected = data.get('faces_detected', 0)
        metrics.faces_parsed = data.get('faces_parsed', 0)
        metrics.faces_rejected = data.get('faces_rejected', 0)
        metrics.processing_time_seconds = data.get('processing_time_seconds', 0.0)
        metrics.baseline_time_seconds = data.get('baseline_time_seconds', 0.0)
        
        if 'roi_count_avg' in data and 'segmentation_runs' in data:
            metrics.total_rois = int(data['roi_count_avg'] * data['segmentation_runs'])
        
        return metrics
