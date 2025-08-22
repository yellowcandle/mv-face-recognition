#!/usr/bin/env python3
"""
Face Detection Accuracy Test for test-video-mv2.mp4
Tests face detection pipeline accuracy, performance, and quality metrics
"""

import cv2
import numpy as np
import yaml
from pathlib import Path
import sys
import time
import logging
from typing import List, Dict, Tuple
import json
from dataclasses import dataclass, asdict

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from face_detector import FaceDetector, ContestantDatabase

# import gpu_memory_manager # Import is already commented out and thus handled, as per ruff check.
from hardware_detector import get_hardware_info

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class DetectionStats:
    """Statistics for face detection analysis"""

    frame_number: int
    timestamp: float
    faces_detected: int
    detection_time: float
    avg_confidence: float
    min_confidence: float
    max_confidence: float
    face_sizes: List[Tuple[int, int]]  # (width, height) for each face


@dataclass
class TestResults:
    """Comprehensive test results"""

    video_info: Dict
    detection_stats: List[DetectionStats]
    overall_performance: Dict
    quality_metrics: Dict
    hardware_info: Dict
    errors: List[str]


class FaceDetectionTester:
    """Face detection accuracy and performance tester"""

    def __init__(self, config_path: str = "config/processing_config.yaml"):
        """Initialize with configuration"""
        self.config_path = Path(config_path)
        self.load_config()
        self.initialize_components()
        self.results = TestResults(
            video_info={},
            detection_stats=[],
            overall_performance={},
            quality_metrics={},
            hardware_info={},
            errors=[],
        )

    def load_config(self):
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, "r") as f:
                self.config = yaml.safe_load(f)
            logger.info(f"Loaded config from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            # Use minimal config if file not found
            self.config = {
                "face_detection": {
                    "model": "insightface",
                    "min_confidence": 0.6,
                    "max_faces_per_frame": 10,
                    "enable_hardware_acceleration": True,
                },
                "contestants": {
                    "photo_dir": "../../source/photo/contestants",
                    "info_csv": "../../source/contestant_info.csv",
                    "embeddings_cache": "data/embeddings_cache.pkl",
                },
            }

    def initialize_components(self):
        """Initialize face detector and contestant database"""
        try:
            # Initialize contestant database
            self.contestant_db = ContestantDatabase(self.config)
            self.contestant_db.load_contestants_info()
            self.contestant_db.build_face_encodings()

            # Initialize face detector
            self.face_detector = FaceDetector(self.config)

            logger.info("Components initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            self.results.errors.append(f"Component initialization failed: {e}")

    def analyze_video_info(self, video_path: Path) -> Dict:
        """Analyze basic video information"""
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"Cannot open video: {video_path}")

            info = {
                "path": str(video_path),
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            }
            info["duration"] = (
                info["frame_count"] / info["fps"] if info["fps"] > 0 else 0
            )
            info["resolution"] = f"{info['width']}x{info['height']}"

            cap.release()

            logger.info(
                f"Video analysis: {info['resolution']}, {info['fps']:.1f}fps, {info['duration']:.1f}s"
            )
            return info

        except Exception as e:
            error_msg = f"Video analysis failed: {e}"
            logger.error(error_msg)
            self.results.errors.append(error_msg)
            return {"error": str(e)}

    def sample_frames_for_testing(
        self, video_info: Dict, sample_count: int = 50
    ) -> List[int]:
        """Generate frame numbers for testing (distributed across video)"""
        if "frame_count" not in video_info:
            return []

        frame_count = video_info["frame_count"]
        if frame_count < sample_count:
            # Use all frames if video is short
            return list(range(0, frame_count, max(1, frame_count // sample_count)))
        else:
            # Sample evenly distributed frames
            step = frame_count // sample_count
            return [i * step for i in range(sample_count)]

    def detect_faces_in_frame(
        self, frame: np.ndarray, frame_number: int, timestamp: float
    ) -> DetectionStats:
        """Detect faces in a single frame and return statistics"""
        start_time = time.time()

        try:
            # Convert BGR to RGB for face detector
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect faces
            detections = self.face_detector.detect_faces(
                rgb_frame, timestamp, frame_number
            )

            detection_time = time.time() - start_time

            # Calculate statistics
            if detections:
                confidences = [d.confidence for d in detections]
                face_sizes = []

                for detection in detections:
                    top, right, bottom, left = detection.location
                    height = bottom - top
                    width = right - left
                    face_sizes.append((width, height))

                stats = DetectionStats(
                    frame_number=frame_number,
                    timestamp=timestamp,
                    faces_detected=len(detections),
                    detection_time=detection_time,
                    avg_confidence=np.mean(confidences) if confidences else 0.0,
                    min_confidence=np.min(confidences) if confidences else 0.0,
                    max_confidence=np.max(confidences) if confidences else 0.0,
                    face_sizes=face_sizes,
                )
            else:
                stats = DetectionStats(
                    frame_number=frame_number,
                    timestamp=timestamp,
                    faces_detected=0,
                    detection_time=detection_time,
                    avg_confidence=0.0,
                    min_confidence=0.0,
                    max_confidence=0.0,
                    face_sizes=[],
                )

            return stats

        except Exception as e:
            error_msg = f"Frame {frame_number} detection failed: {e}"
            logger.error(error_msg)
            self.results.errors.append(error_msg)

            # Return empty stats on error
            return DetectionStats(
                frame_number=frame_number,
                timestamp=timestamp,
                faces_detected=0,
                detection_time=time.time() - start_time,
                avg_confidence=0.0,
                min_confidence=0.0,
                max_confidence=0.0,
                face_sizes=[],
            )

    def test_face_detection_accuracy(self, video_path: Path) -> TestResults:
        """Run comprehensive face detection accuracy test"""
        logger.info(f"Starting face detection accuracy test on {video_path}")

        # Analyze video
        video_info = self.analyze_video_info(video_path)
        self.results.video_info = video_info

        if "error" in video_info:
            return self.results

        # Get hardware info
        try:
            self.results.hardware_info = asdict(get_hardware_info())
        except Exception as e:
            logger.warning(f"Could not get hardware info: {e}")
            self.results.hardware_info = {"error": str(e)}

        # Sample frames for testing
        test_frames = self.sample_frames_for_testing(video_info, sample_count=100)
        logger.info(
            f"Testing {len(test_frames)} frames from {video_info['frame_count']} total"
        )

        # Open video for frame extraction
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            error_msg = f"Cannot open video for testing: {video_path}"
            self.results.errors.append(error_msg)
            return self.results

        detection_stats = []
        fps = video_info.get("fps", 25)

        try:
            for i, frame_number in enumerate(test_frames):
                # Seek to frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()

                if not ret:
                    logger.warning(f"Could not read frame {frame_number}")
                    continue

                timestamp = frame_number / fps
                stats = self.detect_faces_in_frame(frame, frame_number, timestamp)
                detection_stats.append(stats)

                # Progress logging
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(test_frames)} frames")

        except Exception as e:
            error_msg = f"Error during frame processing: {e}"
            logger.error(error_msg)
            self.results.errors.append(error_msg)

        finally:
            cap.release()

        self.results.detection_stats = detection_stats

        # Calculate overall performance metrics
        self.calculate_performance_metrics()
        self.calculate_quality_metrics()

        return self.results

    def calculate_performance_metrics(self):
        """Calculate overall performance metrics"""
        if not self.results.detection_stats:
            return

        detection_times = [s.detection_time for s in self.results.detection_stats]
        faces_per_frame = [s.faces_detected for s in self.results.detection_stats]

        self.results.overall_performance = {
            "avg_detection_time": np.mean(detection_times),
            "min_detection_time": np.min(detection_times),
            "max_detection_time": np.max(detection_times),
            "avg_fps": 1.0 / np.mean(detection_times)
            if np.mean(detection_times) > 0
            else 0,
            "total_frames_tested": len(self.results.detection_stats),
            "avg_faces_per_frame": np.mean(faces_per_frame),
            "max_faces_per_frame": np.max(faces_per_frame),
            "frames_with_faces": sum(
                1 for s in self.results.detection_stats if s.faces_detected > 0
            ),
            "face_detection_rate": sum(
                1 for s in self.results.detection_stats if s.faces_detected > 0
            )
            / len(self.results.detection_stats),
        }

        logger.info(
            f"Performance: {self.results.overall_performance['avg_fps']:.1f} FPS, "
            f"{self.results.overall_performance['avg_faces_per_frame']:.1f} faces/frame"
        )

    def calculate_quality_metrics(self):
        """Calculate quality metrics for face detection"""
        if not self.results.detection_stats:
            return

        # Confidence statistics
        all_confidences = []
        for stat in self.results.detection_stats:
            if stat.faces_detected > 0:
                # Average confidence for frames with faces
                all_confidences.append(stat.avg_confidence)

        # Face size statistics
        all_face_sizes = []
        for stat in self.results.detection_stats:
            all_face_sizes.extend(stat.face_sizes)

        face_areas = [w * h for w, h in all_face_sizes] if all_face_sizes else []

        self.results.quality_metrics = {
            "avg_confidence": np.mean(all_confidences) if all_confidences else 0.0,
            "min_confidence": np.min(all_confidences) if all_confidences else 0.0,
            "max_confidence": np.max(all_confidences) if all_confidences else 0.0,
            "confidence_std": np.std(all_confidences) if all_confidences else 0.0,
            "avg_face_area": np.mean(face_areas) if face_areas else 0.0,
            "min_face_area": np.min(face_areas) if face_areas else 0.0,
            "max_face_area": np.max(face_areas) if face_areas else 0.0,
            "total_faces_detected": sum(
                stat.faces_detected for stat in self.results.detection_stats
            ),
            "meets_expectation_10_faces": self.results.overall_performance.get(
                "avg_faces_per_frame", 0
            )
            >= 10,
        }

    def generate_report(self, output_file: str = "face_detection_test_report.json"):
        """Generate detailed test report"""

        # Convert numpy types to Python types for JSON serialization
        def convert_numpy_types(obj):
            if isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            elif hasattr(obj, "__dict__"):
                return convert_numpy_types(
                    asdict(obj)
                    if hasattr(obj, "__dataclass_fields__")
                    else obj.__dict__
                )
            return obj

        # Convert dataclass to dict with numpy type conversion
        report = convert_numpy_types(asdict(self.results))

        # Add test summary
        summary = {
            "test_status": "PASS" if self.evaluate_test_success() else "FAIL",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config_file": str(self.config_path),
            "key_findings": self.get_key_findings(),
        }
        report["test_summary"] = summary

        # Save report
        output_path = Path(output_file)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Test report saved to {output_path}")
        return report

    def evaluate_test_success(self) -> bool:
        """Evaluate if the test passes acceptance criteria"""
        if not self.results.detection_stats:
            return False

        # Check key criteria
        criteria = [
            # Must detect faces in at least 50% of frames
            self.results.overall_performance.get("face_detection_rate", 0) >= 0.5,
            # Must process at least 1 frame per second
            self.results.overall_performance.get("avg_fps", 0) >= 1.0,
            # Average confidence should be reasonable
            self.results.quality_metrics.get("avg_confidence", 0) >= 0.3,
            # Must detect multiple faces per frame on average
            self.results.overall_performance.get("avg_faces_per_frame", 0) >= 5.0,
            # No major errors
            len(self.results.errors) == 0,
        ]

        return all(criteria)

    def get_key_findings(self) -> List[str]:
        """Get key findings from the test"""
        findings = []

        perf = self.results.overall_performance
        qual = self.results.quality_metrics

        findings.append(f"Tested {perf.get('total_frames_tested', 0)} frames")
        findings.append(
            f"Detection rate: {perf.get('face_detection_rate', 0):.1%} of frames had faces"
        )
        findings.append(f"Performance: {perf.get('avg_fps', 0):.1f} FPS average")
        findings.append(
            f"Accuracy: {perf.get('avg_faces_per_frame', 0):.1f} faces per frame"
        )
        findings.append(
            f"Quality: {qual.get('avg_confidence', 0):.3f} average confidence"
        )

        if qual.get("meets_expectation_10_faces", False):
            findings.append("✅ Meets expectation of >10 faces per frame")
        else:
            findings.append("❌ Does not meet expectation of >10 faces per frame")

        if self.results.errors:
            findings.append(f"⚠️ {len(self.results.errors)} errors occurred")

        return findings

    def print_summary(self):
        """Print test summary to console"""
        print("\n" + "=" * 60)
        print("FACE DETECTION ACCURACY TEST SUMMARY")
        print("=" * 60)

        if self.results.video_info:
            vi = self.results.video_info
            print(f"Video: {Path(vi.get('path', '')).name}")
            print(f"Resolution: {vi.get('resolution', 'Unknown')}")
            print(f"Duration: {vi.get('duration', 0):.1f}s")
            print(f"FPS: {vi.get('fps', 0):.1f}")

        print("\n📊 PERFORMANCE METRICS:")
        perf = self.results.overall_performance
        for key, value in perf.items():
            if isinstance(value, float):
                print(f"  {key.replace('_', ' ').title()}: {value:.3f}")
            else:
                print(f"  {key.replace('_', ' ').title()}: {value}")

        print("\n🎯 QUALITY METRICS:")
        qual = self.results.quality_metrics
        for key, value in qual.items():
            if isinstance(value, bool):
                status = "✅" if value else "❌"
                print(f"  {status} {key.replace('_', ' ').title()}: {value}")
            elif isinstance(value, float):
                print(f"  {key.replace('_', ' ').title()}: {value:.3f}")
            else:
                print(f"  {key.replace('_', ' ').title()}: {value}")

        print(
            f"\n🔧 HARDWARE: {self.results.hardware_info.get('device_name', 'Unknown')}"
        )
        print(f"Backend: {self.results.hardware_info.get('backend', 'Unknown')}")

        if self.results.errors:
            print(f"\n⚠️ ERRORS ({len(self.results.errors)}):")
            for error in self.results.errors[:5]:  # Show first 5 errors
                print(f"  • {error}")

        print("\n📋 KEY FINDINGS:")
        for finding in self.get_key_findings():
            print(f"  • {finding}")

        test_status = "PASS" if self.evaluate_test_success() else "FAIL"
        status_emoji = "✅" if test_status == "PASS" else "❌"
        print(f"\n{status_emoji} TEST STATUS: {test_status}")
        print("=" * 60)


def main():
    """Main test execution"""
    print("🧪 Face Detection Accuracy Testing for test-video-mv2.mp4")
    print("=" * 60)

    # Check if test video exists
    test_video = Path("../source/videos/test-video-mv2.mp4")
    if not test_video.exists():
        print(f"❌ Test video not found: {test_video}")
        print("Available videos:")
        videos_dir = Path("../source/videos")
        if videos_dir.exists():
            for video in videos_dir.glob("*.mp4"):
                print(f"  • {video.name}")
        return 1

    # Initialize tester
    try:
        tester = FaceDetectionTester()
    except Exception as e:
        print(f"❌ Failed to initialize tester: {e}")
        return 1

    # Run test
    try:
        tester.test_face_detection_accuracy(test_video)

        # Print summary
        tester.print_summary()

        # Generate report (skip on error)
        try:
            report_file = f"face_detection_test_report_{int(time.time())}.json"
            tester.generate_report(report_file)
        except Exception as e:
            print(f"⚠️ Could not generate JSON report: {e}")
            print("Results still available in summary above.")

        # Cleanup
        try:
            tester.face_detector.cleanup()
        except:
            pass

        # Return status
        return 0 if tester.evaluate_test_success() else 1

    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
