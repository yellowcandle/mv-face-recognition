#!/usr/bin/env python3
"""
Performance validation for optimized Supervision Face Tracker
Tests the performance improvements made to the ByteTracker implementation
"""

import time
import numpy as np
import psutil
import logging
from typing import List, Dict
from dataclasses import dataclass
import statistics

from src.face_detector import FaceDetection, FaceRecognition
from src.supervision_face_tracker import SupervisionFaceTracker
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for tracking validation"""

    frames_per_second: float
    avg_processing_time: float
    memory_usage_mb: float
    trajectory_count: int
    stable_trajectories: int
    temporal_consistency: float


class OptimizedTrackerValidator:
    """Validation framework for optimized Supervision tracker"""

    def __init__(self, config_path: str = "config/processing_config.yaml"):
        """Initialize validator with configuration"""
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # Force supervision algorithm for testing
        self.config["face_tracking"]["algorithm"] = "supervision"

        self.tracker = SupervisionFaceTracker(self.config)
        logger.info("Optimized tracker validation initialized")

    def generate_test_scenarios(self) -> List[Dict]:
        """Generate realistic test scenarios for face tracking"""
        scenarios = [
            {
                "name": "single_face_simple",
                "description": "Single face detection scenario (optimized path)",
                "num_frames": 100,
                "faces_per_frame": 1,
                "detection_stability": 0.95,
                "movement_pattern": "stable",
            },
            {
                "name": "multi_face_stable",
                "description": "Multiple faces with stable tracking",
                "num_frames": 150,
                "faces_per_frame": 3,
                "detection_stability": 0.90,
                "movement_pattern": "moderate",
            },
            {
                "name": "crowded_scene",
                "description": "Crowded scene with many faces",
                "num_frames": 200,
                "faces_per_frame": 8,
                "detection_stability": 0.75,
                "movement_pattern": "dynamic",
            },
            {
                "name": "high_frame_rate",
                "description": "High frame rate processing test",
                "num_frames": 300,
                "faces_per_frame": 2,
                "detection_stability": 0.85,
                "movement_pattern": "stable",
            },
        ]
        return scenarios

    def generate_synthetic_detections(
        self, scenario: Dict
    ) -> List[List[FaceDetection]]:
        """Generate synthetic face detections for testing"""
        num_frames = scenario["num_frames"]
        faces_per_frame = scenario["faces_per_frame"]
        stability = scenario["detection_stability"]
        movement = scenario["movement_pattern"]

        frame_detections = []

        # Initialize face positions
        face_positions = []
        for face_id in range(faces_per_frame):
            x = 100 + face_id * 200
            y = 100 + (face_id % 2) * 150
            face_positions.append([x, y, x + 120, y + 120])  # [x1, y1, x2, y2]

        movement_speeds = {"stable": 2, "moderate": 8, "dynamic": 20}
        speed = movement_speeds.get(movement, 5)

        for frame_idx in range(num_frames):
            detections = []

            for face_id in range(faces_per_frame):
                # Skip detections based on stability
                if np.random.random() > stability:
                    continue

                # Update position with movement
                if movement != "stable":
                    dx = (np.random.random() - 0.5) * speed
                    dy = (np.random.random() - 0.5) * speed
                    face_positions[face_id][0] += dx
                    face_positions[face_id][1] += dy
                    face_positions[face_id][2] += dx
                    face_positions[face_id][3] += dy

                # Convert to detection format (top, right, bottom, left)
                x1, y1, x2, y2 = face_positions[face_id]
                # Generate dummy face encoding (512-dimensional vector)
                fake_encoding = np.random.random(512).astype(np.float32)
                detection = FaceDetection(
                    location=(
                        int(y1),
                        int(x2),
                        int(y2),
                        int(x1),
                    ),  # top, right, bottom, left
                    encoding=fake_encoding,
                    timestamp=frame_idx / 25.0,  # 25 FPS
                    frame_number=frame_idx,
                    confidence=0.8 + np.random.random() * 0.2,
                )
                detections.append(detection)

            frame_detections.append(detections)

        return frame_detections

    def generate_synthetic_recognitions(
        self, detections: List[FaceDetection]
    ) -> List[FaceRecognition]:
        """Generate synthetic face recognitions"""
        recognitions = []

        for detection in detections:
            # Simulate recognition with some probability
            if np.random.random() > 0.3:
                contestant_id = f"contestant_{(detection.frame_number + hash(str(detection.location))) % 20 + 1:02d}"
                recognition = FaceRecognition(
                    detection=detection,
                    contestant_id=contestant_id,
                    contestant_name=f"Name {contestant_id}",
                    contestant_nickname=f"Nick {contestant_id}",
                    match_confidence=0.6 + np.random.random() * 0.3,
                )
                recognitions.append(recognition)

        return recognitions

    def measure_performance(self, scenario: Dict) -> PerformanceMetrics:
        """Measure performance for a given scenario"""
        logger.info(f"Testing scenario: {scenario['name']}")

        # Generate test data
        frame_detections = self.generate_synthetic_detections(scenario)

        # Reset tracker
        self.tracker.reset()

        # Measure performance
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB

        processing_times = []
        trajectory_counts = []
        consistency_scores = []

        start_time = time.time()

        for frame_idx, detections in enumerate(frame_detections):
            frame_start = time.time()

            # Generate recognitions for this frame
            recognitions = self.generate_synthetic_recognitions(detections)

            # Update tracker
            trajectories = self.tracker.update_trajectories(detections, recognitions)

            frame_end = time.time()
            processing_times.append(frame_end - frame_start)
            trajectory_counts.append(len(trajectories))

            # Calculate temporal consistency (stable trajectories ratio)
            stable_count = sum(1 for t in trajectories if t.is_stable)
            if trajectories:
                consistency = stable_count / len(trajectories)
            else:
                consistency = 1.0
            consistency_scores.append(consistency)

        end_time = time.time()

        memory_after = process.memory_info().rss / 1024 / 1024  # MB

        # Calculate metrics
        total_time = end_time - start_time
        avg_processing_time = (
            statistics.mean(processing_times) if processing_times else 0
        )
        frames_per_second = len(frame_detections) / total_time if total_time > 0 else 0
        avg_trajectories = (
            statistics.mean(trajectory_counts) if trajectory_counts else 0
        )
        stable_trajectories = (
            statistics.mean([max(tc - 1, 0) for tc in trajectory_counts])
            if trajectory_counts
            else 0
        )
        temporal_consistency = (
            statistics.mean(consistency_scores) if consistency_scores else 0
        )

        return PerformanceMetrics(
            frames_per_second=frames_per_second,
            avg_processing_time=avg_processing_time,
            memory_usage_mb=memory_after - memory_before,
            trajectory_count=avg_trajectories,
            stable_trajectories=stable_trajectories,
            temporal_consistency=temporal_consistency,
        )

    def run_validation(self) -> Dict:
        """Run full validation suite"""
        logger.info("Starting optimized tracker validation")

        scenarios = self.generate_test_scenarios()
        results = {}

        for scenario in scenarios:
            try:
                metrics = self.measure_performance(scenario)
                results[scenario["name"]] = {
                    "scenario": scenario,
                    "metrics": metrics,
                    "status": "success",
                }

                logger.info(
                    f"Scenario {scenario['name']}: "
                    f"{metrics.frames_per_second:.1f} FPS, "
                    f"{metrics.avg_processing_time * 1000:.2f}ms/frame, "
                    f"{metrics.memory_usage_mb:.1f}MB"
                )

            except Exception as e:
                logger.error(f"Scenario {scenario['name']} failed: {e}")
                results[scenario["name"]] = {
                    "scenario": scenario,
                    "error": str(e),
                    "status": "failed",
                }

        return results

    def generate_report(self, results: Dict) -> str:
        """Generate performance validation report"""
        report = []
        report.append("# Optimized Supervision Tracker Performance Validation")
        report.append("")
        report.append("## Executive Summary")
        report.append("")

        successful_tests = [r for r in results.values() if r["status"] == "success"]
        [r for r in results.values() if r["status"] == "failed"]

        report.append(f"- **Tests Completed**: {len(successful_tests)}/{len(results)}")
        report.append(
            f"- **Success Rate**: {len(successful_tests) / len(results) * 100:.1f}%"
        )

        if successful_tests:
            avg_fps = statistics.mean(
                [r["metrics"].frames_per_second for r in successful_tests]
            )
            avg_processing = statistics.mean(
                [r["metrics"].avg_processing_time * 1000 for r in successful_tests]
            )
            avg_memory = statistics.mean(
                [r["metrics"].memory_usage_mb for r in successful_tests]
            )

            report.append(
                f"- **Average Performance**: {avg_fps:.1f} FPS, {avg_processing:.2f}ms/frame"
            )
            report.append(f"- **Memory Usage**: {avg_memory:.1f}MB average")

        report.append("")
        report.append("## Detailed Results")
        report.append("")

        for test_name, result in results.items():
            if result["status"] == "success":
                scenario = result["scenario"]
                metrics = result["metrics"]

                report.append(f"### {scenario['name']}")
                report.append(f"**Description**: {scenario['description']}")
                report.append(f"- **Performance**: {metrics.frames_per_second:.1f} FPS")
                report.append(
                    f"- **Processing Time**: {metrics.avg_processing_time * 1000:.2f}ms/frame"
                )
                report.append(f"- **Memory Usage**: {metrics.memory_usage_mb:.1f}MB")
                report.append(
                    f"- **Trajectory Quality**: {metrics.temporal_consistency:.3f}"
                )
                report.append("")
            else:
                report.append(f"### {test_name} (FAILED)")
                report.append(f"**Error**: {result.get('error', 'Unknown error')}")
                report.append("")

        report.append("## Performance Analysis")
        report.append("")

        if successful_tests:
            # Analyze single face optimization
            single_face_results = [
                r for r in successful_tests if "single_face" in r["scenario"]["name"]
            ]
            multi_face_results = [
                r
                for r in successful_tests
                if "single_face" not in r["scenario"]["name"]
            ]

            if single_face_results and multi_face_results:
                single_fps = statistics.mean(
                    [r["metrics"].frames_per_second for r in single_face_results]
                )
                multi_fps = statistics.mean(
                    [r["metrics"].frames_per_second for r in multi_face_results]
                )

                report.append(
                    f"- **Single Face Optimization**: {single_fps:.1f} FPS vs {multi_fps:.1f} FPS multi-face"
                )
                report.append(
                    f"- **Performance Improvement**: {((single_fps / multi_fps - 1) * 100):.1f}% faster for single face"
                )

        report.append("")
        report.append("## Optimization Impact")
        report.append("")
        report.append("Key optimizations implemented:")
        report.append(
            "1. **Array Reuse**: Pre-allocated arrays for detection conversion"
        )
        report.append(
            "2. **Parameter Tuning**: Optimized ByteTracker parameters for face tracking"
        )
        report.append(
            "3. **Single Face Optimization**: Streamlined processing for simple scenes"
        )
        report.append(
            "4. **Recognition Caching**: Efficient lookup using cached mappings"
        )
        report.append(
            "5. **Adaptive Tracking**: Context-aware processing based on scene complexity"
        )

        return "\n".join(report)


def main():
    """Run optimized tracker validation"""
    validator = OptimizedTrackerValidator()

    # Run validation
    results = validator.run_validation()

    # Generate report
    report = validator.generate_report(results)

    # Save report
    with open("optimized_tracker_validation_report.md", "w") as f:
        f.write(report)

    print(report)
    print(
        "\nValidation complete! Report saved to optimized_tracker_validation_report.md"
    )


if __name__ == "__main__":
    main()
