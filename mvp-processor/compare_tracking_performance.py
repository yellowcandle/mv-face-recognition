#!/usr/bin/env python3
"""
Performance Comparison: Custom Face Tracker vs Supervision ByteTracker
Compares tracking accuracy, temporal consistency, and performance metrics
"""

import time
import numpy as np
import yaml
from pathlib import Path
from typing import Dict, List, Tuple
import logging
import json
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from face_tracker import FaceTracker as CustomFaceTracker
from supervision_face_tracker import SupervisionFaceTracker
from face_detector import FaceDetection, FaceRecognition

logger = logging.getLogger(__name__)


class TrackingPerformanceAnalyzer:
    """Analyze and compare tracking performance between implementations"""
    
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize both trackers
        self.custom_tracker = CustomFaceTracker(self.config)
        self.supervision_tracker = SupervisionFaceTracker(self.config)
        
        # Performance metrics
        self.metrics = {
            'custom': {
                'processing_time': [],
                'trajectory_count': [],
                'stable_trajectories': [],
                'memory_usage': [],
                'trajectory_consistency': []
            },
            'supervision': {
                'processing_time': [],
                'trajectory_count': [],
                'stable_trajectories': [],
                'memory_usage': [],
                'trajectory_consistency': []
            }
        }
        
    def generate_synthetic_detections(self, num_frames: int = 100, faces_per_frame: int = 3) -> List[Tuple[List[FaceDetection], List[FaceRecognition]]]:
        """Generate synthetic face detections for testing"""
        data = []
        
        # Simulate face movement across frames
        face_positions = {}
        
        for frame_idx in range(num_frames):
            frame_detections = []
            frame_recognitions = []
            
            # Add some consistent faces (trajectory simulation)
            for face_id in range(min(faces_per_frame, 3)):
                if face_id not in face_positions:
                    # Initialize random position
                    face_positions[face_id] = {
                        'x': np.random.randint(100, 500),
                        'y': np.random.randint(100, 300),
                        'width': np.random.randint(50, 100),
                        'height': np.random.randint(50, 100)
                    }
                
                # Add small random movement
                pos = face_positions[face_id]
                pos['x'] += np.random.randint(-10, 11)
                pos['y'] += np.random.randint(-5, 6)
                
                # Create detection
                location = (
                    pos['y'],  # top
                    pos['x'] + pos['width'],  # right
                    pos['y'] + pos['height'],  # bottom
                    pos['x']  # left
                )
                
                detection = FaceDetection(
                    location=location,
                    encoding=np.random.rand(128),  # Mock face encoding
                    timestamp=frame_idx * 0.167,  # 6 FPS
                    frame_number=frame_idx,
                    confidence=0.8 + np.random.rand() * 0.2
                )
                
                frame_detections.append(detection)
                
                # Create mock recognition (simulate some faces being recognized)
                if np.random.rand() > 0.3:  # 70% recognition rate
                    contestant_id = str(np.random.randint(1, 96))
                    recognition = FaceRecognition(
                        detection=detection,
                        contestant_id=contestant_id,
                        contestant_name=f"Contestant_{contestant_id}",
                        contestant_nickname=f"Nick_{contestant_id}",
                        match_confidence=0.5 + np.random.rand() * 0.5
                    )
                    frame_recognitions.append(recognition)
            
            # Occasionally add/remove faces (simulate faces entering/leaving scene)
            if np.random.rand() > 0.9:  # 10% chance
                if len(face_positions) > 1 and np.random.rand() > 0.5:
                    # Remove a face
                    face_to_remove = np.random.choice(list(face_positions.keys()))
                    del face_positions[face_to_remove]
                else:
                    # Add a new face
                    new_face_id = max(face_positions.keys()) + 1 if face_positions else 0
                    face_positions[new_face_id] = {
                        'x': np.random.randint(100, 500),
                        'y': np.random.randint(100, 300),
                        'width': np.random.randint(50, 100),
                        'height': np.random.randint(50, 100)
                    }
            
            data.append((frame_detections, frame_recognitions))
        
        return data
    
    def measure_memory_usage(self) -> float:
        """Estimate memory usage (simplified)"""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    
    def calculate_trajectory_consistency(self, trajectories: List) -> float:
        """Calculate trajectory temporal consistency score"""
        if not trajectories:
            return 0.0
        
        consistency_scores = []
        for trajectory in trajectories:
            if len(trajectory.detections) < 2:
                continue
            
            # Calculate position stability
            positions = []
            for detection in trajectory.detections:
                top, right, bottom, left = detection.location
                center_x = (left + right) / 2
                center_y = (top + bottom) / 2
                positions.append((center_x, center_y))
            
            # Calculate movement variance
            if len(positions) > 1:
                movements = []
                for i in range(1, len(positions)):
                    dx = positions[i][0] - positions[i-1][0]
                    dy = positions[i][1] - positions[i-1][1]
                    movement = np.sqrt(dx*dx + dy*dy)
                    movements.append(movement)
                
                # Lower variance = higher consistency
                movement_variance = np.var(movements)
                consistency = 1.0 / (1.0 + movement_variance / 100.0)  # Normalize
                consistency_scores.append(consistency)
        
        return np.mean(consistency_scores) if consistency_scores else 0.0
    
    def run_tracker_comparison(self, test_data: List[Tuple[List[FaceDetection], List[FaceRecognition]]], 
                             tracker_name: str, tracker) -> Dict:
        """Run tracking on test data and collect metrics"""
        results = {
            'total_time': 0.0,
            'avg_time_per_frame': 0.0,
            'trajectory_stats': [],
            'consistency_scores': [],
            'memory_usage': []
        }
        
        tracker.reset()
        start_time = time.time()
        
        for frame_idx, (detections, recognitions) in enumerate(test_data):
            frame_start = time.time()
            
            # Update tracker
            trajectories = tracker.update_trajectories(detections, recognitions)
            
            frame_time = time.time() - frame_start
            self.metrics[tracker_name]['processing_time'].append(frame_time)
            
            # Collect statistics
            stats = tracker.get_tracking_stats()
            self.metrics[tracker_name]['trajectory_count'].append(stats['active_trajectories'])
            self.metrics[tracker_name]['stable_trajectories'].append(stats['stable_trajectories'])
            
            # Calculate trajectory consistency
            consistency = self.calculate_trajectory_consistency(trajectories)
            self.metrics[tracker_name]['trajectory_consistency'].append(consistency)
            
            # Memory usage (sample every 10 frames)
            if frame_idx % 10 == 0:
                memory = self.measure_memory_usage()
                self.metrics[tracker_name]['memory_usage'].append(memory)
        
        total_time = time.time() - start_time
        results['total_time'] = total_time
        results['avg_time_per_frame'] = total_time / len(test_data)
        results['final_stats'] = tracker.get_tracking_stats()
        
        return results
    
    def run_comparison(self, num_frames: int = 100, faces_per_frame: int = 3) -> Dict:
        """Run complete comparison between trackers"""
        logger.info(f"Starting tracking comparison with {num_frames} frames, {faces_per_frame} faces per frame")
        
        # Generate test data
        test_data = self.generate_synthetic_detections(num_frames, faces_per_frame)
        logger.info(f"Generated {len(test_data)} frames of test data")
        
        # Test custom tracker
        logger.info("Testing custom FaceTracker...")
        custom_results = self.run_tracker_comparison(test_data, 'custom', self.custom_tracker)
        
        # Test supervision tracker
        logger.info("Testing SupervisionFaceTracker...")
        supervision_results = self.run_tracker_comparison(test_data, 'supervision', self.supervision_tracker)
        
        # Calculate comparative metrics
        comparison = self._analyze_results(custom_results, supervision_results)
        
        return {
            'test_config': {
                'num_frames': num_frames,
                'faces_per_frame': faces_per_frame,
                'total_detections': sum(len(dets) for dets, _ in test_data)
            },
            'custom_tracker': custom_results,
            'supervision_tracker': supervision_results,
            'comparison': comparison,
            'detailed_metrics': self.metrics
        }
    
    def _analyze_results(self, custom_results: Dict, supervision_results: Dict) -> Dict:
        """Analyze and compare results between trackers"""
        custom_metrics = self.metrics['custom']
        supervision_metrics = self.metrics['supervision']
        
        comparison = {
            'performance': {
                'custom_avg_time': np.mean(custom_metrics['processing_time']),
                'supervision_avg_time': np.mean(supervision_metrics['processing_time']),
                'speed_improvement': None,
                'winner': None
            },
            'tracking_quality': {
                'custom_avg_trajectories': np.mean(custom_metrics['trajectory_count']),
                'supervision_avg_trajectories': np.mean(supervision_metrics['trajectory_count']),
                'custom_avg_stable': np.mean(custom_metrics['stable_trajectories']),
                'supervision_avg_stable': np.mean(supervision_metrics['stable_trajectories']),
                'stability_improvement': None,
                'consistency_improvement': None
            },
            'memory_efficiency': {
                'custom_avg_memory': np.mean(custom_metrics['memory_usage']) if custom_metrics['memory_usage'] else 0,
                'supervision_avg_memory': np.mean(supervision_metrics['memory_usage']) if supervision_metrics['memory_usage'] else 0,
                'memory_improvement': None
            }
        }
        
        # Calculate improvements
        if comparison['performance']['custom_avg_time'] > 0:
            speed_ratio = comparison['performance']['custom_avg_time'] / comparison['performance']['supervision_avg_time']
            comparison['performance']['speed_improvement'] = (speed_ratio - 1) * 100
            comparison['performance']['winner'] = 'supervision' if speed_ratio > 1 else 'custom'
        
        custom_consistency = np.mean(custom_metrics['trajectory_consistency'])
        supervision_consistency = np.mean(supervision_metrics['trajectory_consistency'])
        if custom_consistency > 0:
            comparison['tracking_quality']['consistency_improvement'] = \
                ((supervision_consistency - custom_consistency) / custom_consistency) * 100
        
        if comparison['tracking_quality']['custom_avg_stable'] > 0:
            stability_ratio = comparison['tracking_quality']['supervision_avg_stable'] / comparison['tracking_quality']['custom_avg_stable']
            comparison['tracking_quality']['stability_improvement'] = (stability_ratio - 1) * 100
        
        if comparison['memory_efficiency']['custom_avg_memory'] > 0:
            memory_ratio = comparison['memory_efficiency']['custom_avg_memory'] / comparison['memory_efficiency']['supervision_avg_memory']
            comparison['memory_efficiency']['memory_improvement'] = (memory_ratio - 1) * 100
        
        return comparison


def main():
    """Main comparison function"""
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Configuration path
    config_path = Path(__file__).parent / 'config' / 'processing_config.yaml'
    
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        return
    
    try:
        analyzer = TrackingPerformanceAnalyzer(str(config_path))
        
        # Run comparison with different scenarios
        scenarios = [
            {'num_frames': 50, 'faces_per_frame': 2},   # Light load
            {'num_frames': 100, 'faces_per_frame': 3},  # Medium load
            {'num_frames': 200, 'faces_per_frame': 5},  # Heavy load
        ]
        
        all_results = {}
        
        for i, scenario in enumerate(scenarios):
            logger.info(f"Running scenario {i+1}: {scenario}")
            results = analyzer.run_comparison(**scenario)
            all_results[f"scenario_{i+1}"] = results
        
        # Save results
        output_file = Path(__file__).parent / 'tracking_comparison_results.json'
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        logger.info(f"Results saved to {output_file}")
        
        # Print summary
        print("\n" + "="*80)
        print("TRACKING PERFORMANCE COMPARISON SUMMARY")
        print("="*80)
        
        for scenario_name, results in all_results.items():
            comp = results['comparison']
            print(f"\n{scenario_name.upper()}:")
            print(f"  Test: {results['test_config']['num_frames']} frames, {results['test_config']['faces_per_frame']} faces/frame")
            print(f"  Speed: {comp['performance']['speed_improvement']:+.1f}% (Supervision vs Custom)")
            print(f"  Consistency: {comp['tracking_quality']['consistency_improvement']:+.1f}%")
            print(f"  Stability: {comp['tracking_quality']['stability_improvement']:+.1f}%")
            print(f"  Memory: {comp['memory_efficiency']['memory_improvement']:+.1f}%")
            print(f"  Winner: {comp['performance']['winner']}")
        
        print("\n" + "="*80)
        
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()