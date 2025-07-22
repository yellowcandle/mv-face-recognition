#!/usr/bin/env python3
"""
Temporal Face Tracking Validation Test
Tests the face tracking system using test-video-mv2.mp4 data
"""

import sys
import os
import json
import yaml
import numpy as np
from pathlib import Path
from typing import Dict, List
import logging

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from face_tracker import FaceTracker, FaceTrajectory
from face_detector import FaceDetection, FaceRecognition

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FrameTestData:
    """Test data structure for frame analysis"""

    def __init__(self, frame_data: dict):
        self.frame_number = frame_data["frame_number"]
        self.timestamp = frame_data["timestamp"]
        self.detections_count = frame_data["detections_count"]
        self.recognitions_count = frame_data["recognitions_count"]
        self.recognitions = frame_data["recognitions"]


class TemporalTrackingValidator:
    """Validates temporal face tracking system performance"""

    def __init__(self):
        self.config = self.load_config()
        self.frame_data: List[FrameTestData] = []
        self.metadata = None

        # Initialize face tracker
        self.face_tracker = FaceTracker(self.config)
        logger.info("TemporalTrackingValidator initialized")

    def load_config(self) -> dict:
        """Load tracking configuration"""
        config_path = Path(__file__).parent / "config" / "processing_config.yaml"
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def load_test_metadata(self) -> bool:
        """Load test video metadata"""
        metadata_path = (
            Path(__file__).parent.parent / "metadata" / "test-video-mv2_metadata.json"
        )
        if not metadata_path.exists():
            logger.error(f"Test metadata not found: {metadata_path}")
            return False

        with open(metadata_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        # Convert to test data structures
        for frame_data in self.metadata["frame_data"]:
            self.frame_data.append(FrameTestData(frame_data))

        logger.info(f"Loaded {len(self.frame_data)} frames of test data")
        return True

    def create_mock_detections(
        self, frame_test_data: FrameTestData
    ) -> List[FaceDetection]:
        """Create mock FaceDetection objects from test data"""
        detections = []

        # For frames with recognitions, use the recognition face locations
        for recognition_data in frame_test_data.recognitions:
            face_location = tuple(recognition_data["face_location"])
            # Create mock encoding (128-dimensional vector)
            mock_encoding = np.random.rand(128).astype(np.float32)

            detection = FaceDetection(
                location=face_location,
                encoding=mock_encoding,
                confidence=0.8,  # Mock detection confidence
                timestamp=frame_test_data.timestamp,
                frame_number=frame_test_data.frame_number,
            )
            detections.append(detection)

        # For frames with detections but no recognitions, create mock locations
        remaining_detections = frame_test_data.detections_count - len(detections)
        for i in range(remaining_detections):
            # Create mock face locations spread across the frame
            x_offset = i * 200
            y_offset = (i % 2) * 100 + 200

            mock_location = (
                y_offset,  # top
                x_offset + 150,  # right
                y_offset + 100,  # bottom
                x_offset + 50,  # left
            )

            # Create mock encoding (128-dimensional vector)
            mock_encoding = np.random.rand(128).astype(np.float32)

            detection = FaceDetection(
                location=mock_location,
                encoding=mock_encoding,
                confidence=0.7,
                timestamp=frame_test_data.timestamp,
                frame_number=frame_test_data.frame_number,
            )
            detections.append(detection)

        return detections

    def create_mock_recognitions(
        self, frame_test_data: FrameTestData, detections: List[FaceDetection]
    ) -> List[FaceRecognition]:
        """Create mock FaceRecognition objects from test data"""
        recognitions = []

        for i, recognition_data in enumerate(frame_test_data.recognitions):
            if i < len(detections):
                recognition = FaceRecognition(
                    detection=detections[i],
                    contestant_id=recognition_data["contestant_id"],
                    contestant_name=recognition_data["contestant_name"],
                    contestant_nickname=recognition_data["contestant_nickname"],
                    match_confidence=recognition_data["confidence"],
                )
                recognitions.append(recognition)

        return recognitions

    def test_spatial_correlation_iou(self) -> Dict:
        """Test IoU calculation for spatial correlation"""
        logger.info("Testing spatial correlation (IoU matching)...")

        # Test different IoU scenarios
        test_cases = [
            # Format: (box1, box2, expected_iou_range)
            (
                (100, 200, 200, 100),
                (100, 200, 200, 100),
                (0.95, 1.05),
            ),  # Perfect overlap
            (
                (100, 200, 200, 100),
                (110, 210, 210, 110),
                (0.6, 0.8),
            ),  # Significant overlap
            ((100, 200, 200, 100), (150, 250, 250, 150), (0.1, 0.3)),  # Partial overlap
            ((100, 200, 200, 100), (300, 400, 400, 300), (-0.01, 0.01)),  # No overlap
        ]

        results = {
            "test_cases_passed": 0,
            "test_cases_total": len(test_cases),
            "iou_calculations": [],
        }

        for i, (box1, box2, expected_range) in enumerate(test_cases):
            iou = self.face_tracker.calculate_iou(box1, box2)
            min_expected, max_expected = expected_range

            test_passed = min_expected <= iou <= max_expected
            if test_passed:
                results["test_cases_passed"] += 1

            results["iou_calculations"].append(
                {
                    "test_case": i + 1,
                    "box1": box1,
                    "box2": box2,
                    "calculated_iou": iou,
                    "expected_range": expected_range,
                    "passed": test_passed,
                }
            )

            logger.info(
                f"IoU test {i + 1}: {iou:.3f} (expected {min_expected:.1f}-{max_expected:.1f}) {'✓' if test_passed else '✗'}"
            )

        results["success_rate"] = (
            results["test_cases_passed"] / results["test_cases_total"]
        )
        logger.info(
            f"IoU testing complete: {results['test_cases_passed']}/{results['test_cases_total']} passed"
        )

        return results

    def test_trajectory_creation_and_management(self) -> Dict:
        """Test trajectory creation, maintenance, and expiration"""
        logger.info("Testing trajectory creation and management...")

        # Reset tracker for clean test
        self.face_tracker.reset()

        trajectory_stats = {
            "trajectories_created": 0,
            "trajectories_expired": 0,
            "max_active_trajectories": 0,
            "frame_processing_stats": [],
            "trajectory_durations": [],
            "stability_statistics": {
                "stable_trajectories_count": 0,
                "unstable_trajectories_count": 0,
            },
        }

        # Process each frame and track trajectory management
        for frame_idx, frame_test_data in enumerate(self.frame_data):
            detections = self.create_mock_detections(frame_test_data)
            recognitions = self.create_mock_recognitions(frame_test_data, detections)

            # Update trajectories
            active_trajectories = self.face_tracker.update_trajectories(
                detections, recognitions
            )

            # Track statistics
            current_active = len(active_trajectories)
            current_completed = len(self.face_tracker.completed_trajectories)
            stable_count = sum(1 for t in active_trajectories if t.is_stable)

            trajectory_stats["max_active_trajectories"] = max(
                trajectory_stats["max_active_trajectories"], current_active
            )

            frame_stats = {
                "frame_number": frame_test_data.frame_number,
                "timestamp": frame_test_data.timestamp,
                "active_trajectories": current_active,
                "completed_trajectories": current_completed,
                "stable_trajectories": stable_count,
                "detections_count": len(detections),
                "recognitions_count": len(recognitions),
            }

            trajectory_stats["frame_processing_stats"].append(frame_stats)

            # Log progress every 30 frames
            if frame_idx % 30 == 0:
                logger.info(
                    f"Frame {frame_test_data.frame_number}: {current_active} active, {stable_count} stable trajectories"
                )

        # Final statistics
        final_stats = self.face_tracker.get_tracking_stats()
        trajectory_stats["trajectories_created"] = final_stats["next_trajectory_id"] - 1
        trajectory_stats["trajectories_expired"] = final_stats["completed_trajectories"]

        # Calculate trajectory durations
        for trajectory in self.face_tracker.completed_trajectories:
            duration = trajectory.get_trajectory_duration()
            trajectory_stats["trajectory_durations"].append(duration)

            if trajectory.is_stable:
                trajectory_stats["stability_statistics"][
                    "stable_trajectories_count"
                ] += 1
            else:
                trajectory_stats["stability_statistics"][
                    "unstable_trajectories_count"
                ] += 1

        # Calculate averages
        if trajectory_stats["trajectory_durations"]:
            trajectory_stats["average_trajectory_duration"] = np.mean(
                trajectory_stats["trajectory_durations"]
            )
            trajectory_stats["median_trajectory_duration"] = np.median(
                trajectory_stats["trajectory_durations"]
            )
        else:
            trajectory_stats["average_trajectory_duration"] = 0.0
            trajectory_stats["median_trajectory_duration"] = 0.0

        logger.info("Trajectory management test complete:")
        logger.info(
            f"  Created: {trajectory_stats['trajectories_created']} trajectories"
        )
        logger.info(
            f"  Expired: {trajectory_stats['trajectories_expired']} trajectories"
        )
        logger.info(
            f"  Max active: {trajectory_stats['max_active_trajectories']} trajectories"
        )
        logger.info(
            f"  Average duration: {trajectory_stats['average_trajectory_duration']:.2f}s"
        )

        return trajectory_stats

    def test_confidence_aggregation(self) -> Dict:
        """Test temporal confidence aggregation across frame sequences"""
        logger.info("Testing temporal confidence aggregation...")

        # Create a controlled test scenario with known confidence patterns
        test_trajectory = FaceTrajectory(trajectory_id=999, first_frame=0, last_frame=0)

        # Test confidence decay with realistic values
        confidence_sequence = [0.8, 0.75, 0.9, 0.85, 0.7, 0.95, 0.8]
        timestamps = [
            i * 0.16 for i in range(len(confidence_sequence))
        ]  # 6 FPS sampling
        frame_numbers = [i * 4 for i in range(len(confidence_sequence))]  # 25 FPS video

        aggregation_results = {
            "confidence_sequence": confidence_sequence,
            "aggregated_confidences": [],
            "decay_factor": self.config.get("face_tracking", {}).get(
                "confidence_smoothing", 0.95
            ),
            "final_aggregated_confidence": 0.0,
            "stability_achieved": False,
        }

        # Add detections with known confidences
        for i, (conf, timestamp, frame_num) in enumerate(
            zip(confidence_sequence, timestamps, frame_numbers)
        ):
            # Create mock detection and recognition
            mock_encoding = np.random.rand(128).astype(np.float32)
            detection = FaceDetection(
                location=(200, 300, 300, 200),
                encoding=mock_encoding,
                confidence=0.8,
                timestamp=timestamp,
                frame_number=frame_num,
            )

            recognition = FaceRecognition(
                detection=detection,
                contestant_id="test_contestant",
                contestant_name="Test Contestant",
                contestant_nickname="Test",
                match_confidence=conf,
            )

            # Add to trajectory with tracking config
            test_trajectory.add_detection(
                detection, recognition, self.config.get("face_tracking", {})
            )

            aggregation_results["aggregated_confidences"].append(
                test_trajectory.aggregated_confidence
            )

            logger.info(
                f"Frame {frame_num}: confidence {conf:.3f} -> aggregated {test_trajectory.aggregated_confidence:.3f}"
            )

        aggregation_results["final_aggregated_confidence"] = (
            test_trajectory.aggregated_confidence
        )
        aggregation_results["stability_achieved"] = test_trajectory.is_stable

        # Test confidence decay properties
        smoothing_factor = aggregation_results["decay_factor"]
        expected_properties = {
            "recent_bias": "More recent frames should have higher weight",
            "smoothing_effect": f"Decay factor {smoothing_factor} should smooth noise",
            "stability_threshold": "Should achieve stability with multiple confident detections",
        }

        aggregation_results["validation_properties"] = expected_properties

        logger.info("Confidence aggregation test complete:")
        logger.info(
            f"  Final aggregated confidence: {aggregation_results['final_aggregated_confidence']:.3f}"
        )
        logger.info(
            f"  Stability achieved: {aggregation_results['stability_achieved']}"
        )
        logger.info(f"  Decay factor: {aggregation_results['decay_factor']}")

        return aggregation_results

    def test_tracking_statistics_generation(self) -> Dict:
        """Test tracking statistics generation and reasonableness"""
        logger.info("Testing tracking statistics generation...")

        # Get current tracking statistics
        stats = self.face_tracker.get_tracking_stats()

        # Validate statistics structure and reasonableness
        validation_results = {
            "statistics_structure": {},
            "reasonableness_checks": {},
            "validation_passed": True,
        }

        # Check required statistics fields
        required_fields = [
            "active_trajectories",
            "completed_trajectories",
            "stable_trajectories",
            "average_trajectory_duration",
            "next_trajectory_id",
        ]

        for field in required_fields:
            if field in stats:
                validation_results["statistics_structure"][field] = {
                    "present": True,
                    "value": stats[field],
                    "type": type(stats[field]).__name__,
                }
            else:
                validation_results["statistics_structure"][field] = {
                    "present": False,
                    "expected": True,
                }
                validation_results["validation_passed"] = False

        # Reasonableness checks
        checks = []

        # Check that trajectory IDs are positive
        if stats.get("next_trajectory_id", 0) >= 1:
            checks.append(
                {
                    "check": "positive_trajectory_ids",
                    "passed": True,
                    "value": stats["next_trajectory_id"],
                }
            )
        else:
            checks.append(
                {
                    "check": "positive_trajectory_ids",
                    "passed": False,
                    "value": stats.get("next_trajectory_id", 0),
                }
            )
            validation_results["validation_passed"] = False

        # Check that active + completed >= created - 1
        total_trajectories = stats.get("next_trajectory_id", 1) - 1
        active = stats.get("active_trajectories", 0)
        completed = stats.get("completed_trajectories", 0)
        accounted_trajectories = active + completed

        if accounted_trajectories >= 0 and accounted_trajectories <= total_trajectories:
            checks.append(
                {
                    "check": "trajectory_accounting",
                    "passed": True,
                    "total": total_trajectories,
                    "accounted": accounted_trajectories,
                }
            )
        else:
            checks.append(
                {
                    "check": "trajectory_accounting",
                    "passed": False,
                    "total": total_trajectories,
                    "accounted": accounted_trajectories,
                }
            )
            validation_results["validation_passed"] = False

        # Check average duration is reasonable (0-30s for a 30s video)
        avg_duration = stats.get("average_trajectory_duration", 0)
        if 0 <= avg_duration <= 30.0:
            checks.append(
                {
                    "check": "reasonable_avg_duration",
                    "passed": True,
                    "value": avg_duration,
                }
            )
        else:
            checks.append(
                {
                    "check": "reasonable_avg_duration",
                    "passed": False,
                    "value": avg_duration,
                }
            )
            validation_results["validation_passed"] = False

        validation_results["reasonableness_checks"] = checks
        validation_results["raw_statistics"] = stats

        logger.info(
            f"Statistics validation: {'✓ PASSED' if validation_results['validation_passed'] else '✗ FAILED'}"
        )
        for check in checks:
            status = "✓" if check["passed"] else "✗"
            logger.info(f"  {status} {check['check']}: {check.get('value', 'N/A')}")

        return validation_results

    def generate_comprehensive_report(self, test_results: Dict) -> Dict:
        """Generate comprehensive tracking performance report"""
        logger.info("Generating comprehensive tracking performance report...")

        report = {
            "test_summary": {
                "test_video": "test-video-mv2.mp4",
                "test_timestamp": self.metadata["processing_summary"][
                    "processing_timestamp"
                ],
                "frames_analyzed": len(self.frame_data),
                "total_detections": self.metadata["processing_summary"][
                    "total_faces_detected"
                ],
                "total_recognitions": self.metadata["processing_summary"][
                    "total_recognitions"
                ],
            },
            "configuration_tested": {
                "tracking_window": self.config.get("face_tracking", {}).get(
                    "tracking_window", "N/A"
                ),
                "spatial_threshold": self.config.get("face_tracking", {}).get(
                    "spatial_threshold", "N/A"
                ),
                "confidence_smoothing": self.config.get("face_tracking", {}).get(
                    "confidence_smoothing", "N/A"
                ),
                "max_trajectory_gap": self.config.get("face_tracking", {}).get(
                    "max_trajectory_gap", "N/A"
                ),
            },
            "test_results": test_results,
            "acceptance_criteria_validation": {},
            "recommendations": [],
        }

        # Validate against acceptance criteria
        criteria = {
            "spatial_correlation_effectiveness": {
                "target": "> 80% IoU calculations accurate",
                "actual": test_results["iou_results"]["success_rate"] * 100,
                "passed": test_results["iou_results"]["success_rate"] > 0.8,
            },
            "trajectory_creation_rate": {
                "target": "> 0 trajectories created for video with faces",
                "actual": test_results["trajectory_stats"]["trajectories_created"],
                "passed": test_results["trajectory_stats"]["trajectories_created"] > 0,
            },
            "confidence_aggregation_stability": {
                "target": "Aggregated confidence computed without errors",
                "actual": test_results["confidence_test"][
                    "final_aggregated_confidence"
                ],
                "passed": test_results["confidence_test"]["final_aggregated_confidence"]
                > 0,
            },
            "statistics_generation_completeness": {
                "target": "All required statistics fields present and valid",
                "actual": test_results["statistics_validation"]["validation_passed"],
                "passed": test_results["statistics_validation"]["validation_passed"],
            },
        }

        overall_passed = all(criterion["passed"] for criterion in criteria.values())

        report["acceptance_criteria_validation"] = {
            "overall_passed": overall_passed,
            "criteria": criteria,
        }

        # Generate recommendations
        if test_results["iou_results"]["success_rate"] < 0.9:
            report["recommendations"].append(
                "Consider tuning spatial_threshold for better IoU matching accuracy"
            )

        if test_results["trajectory_stats"]["max_active_trajectories"] < 5:
            report["recommendations"].append(
                "Test with more complex scenes to validate multi-face tracking"
            )

        if test_results["trajectory_stats"]["average_trajectory_duration"] < 1.0:
            report["recommendations"].append(
                "Consider increasing tracking_window for longer trajectory persistence"
            )

        if not test_results["confidence_test"]["stability_achieved"]:
            report["recommendations"].append(
                "Review confidence_threshold and min_stable_detections parameters"
            )

        logger.info(
            f"Report generation complete. Overall acceptance: {'✓ PASSED' if overall_passed else '✗ FAILED'}"
        )

        return report

    def run_full_test_suite(self) -> Dict:
        """Run complete temporal tracking validation test suite"""
        logger.info("=" * 60)
        logger.info("Starting Temporal Face Tracking Validation Test Suite")
        logger.info("=" * 60)

        if not self.load_test_metadata():
            return {"error": "Failed to load test metadata"}

        test_results = {}

        # Test 1: Spatial correlation (IoU matching)
        logger.info("\n" + "=" * 40)
        logger.info("TEST 1: Spatial Correlation (IoU)")
        logger.info("=" * 40)
        test_results["iou_results"] = self.test_spatial_correlation_iou()

        # Test 2: Trajectory creation and management
        logger.info("\n" + "=" * 40)
        logger.info("TEST 2: Trajectory Management")
        logger.info("=" * 40)
        test_results["trajectory_stats"] = (
            self.test_trajectory_creation_and_management()
        )

        # Test 3: Confidence aggregation
        logger.info("\n" + "=" * 40)
        logger.info("TEST 3: Confidence Aggregation")
        logger.info("=" * 40)
        test_results["confidence_test"] = self.test_confidence_aggregation()

        # Test 4: Statistics generation
        logger.info("\n" + "=" * 40)
        logger.info("TEST 4: Statistics Validation")
        logger.info("=" * 40)
        test_results["statistics_validation"] = (
            self.test_tracking_statistics_generation()
        )

        # Generate comprehensive report
        logger.info("\n" + "=" * 40)
        logger.info("GENERATING COMPREHENSIVE REPORT")
        logger.info("=" * 40)
        report = self.generate_comprehensive_report(test_results)

        logger.info("\n" + "=" * 60)
        logger.info("TEMPORAL TRACKING VALIDATION COMPLETE")
        logger.info("=" * 60)

        return report


def main():
    """Main test execution"""
    validator = TemporalTrackingValidator()

    try:
        report = validator.run_full_test_suite()

        # Save report
        report_path = Path(__file__).parent / "temporal_tracking_validation_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Full report saved to: {report_path}")

        # Print summary
        print("\n" + "=" * 60)
        print("TEMPORAL TRACKING VALIDATION SUMMARY")
        print("=" * 60)

        if "error" in report:
            print(f"❌ Test failed: {report['error']}")
            return 1

        overall_passed = report.get("acceptance_criteria_validation", {}).get(
            "overall_passed", False
        )

        print(f"Overall Result: {'✅ PASSED' if overall_passed else '❌ FAILED'}")
        print(f"Video: {report['test_summary']['test_video']}")
        print(f"Frames Analyzed: {report['test_summary']['frames_analyzed']}")
        print(f"Total Detections: {report['test_summary']['total_detections']}")
        print(f"Total Recognitions: {report['test_summary']['total_recognitions']}")

        print("\nAcceptance Criteria:")
        for criterion_name, criterion in (
            report.get("acceptance_criteria_validation", {}).get("criteria", {}).items()
        ):
            status = "✅" if criterion["passed"] else "❌"
            print(
                f"  {status} {criterion_name}: {criterion['actual']} ({criterion['target']})"
            )

        if report.get("recommendations"):
            print("\nRecommendations:")
            for rec in report["recommendations"]:
                print(f"  • {rec}")

        print("\n" + "=" * 60)

        return 0 if overall_passed else 1

    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
