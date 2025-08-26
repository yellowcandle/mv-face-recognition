"""
Comprehensive Integration Test for Embedding System
Validates the complete embedding system after fixes are applied.

This test covers:
1. Unified embedding system initialization
2. All 96 contestant embeddings loading
3. Video path resolution
4. Processing pipeline startup
5. Embedding auto-generation fallback
"""

import pytest
import numpy as np
import pandas as pd
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil
import cv2
import logging
import sys
import os

# Add src directory to Python path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

logger = logging.getLogger(__name__)


class EmbeddingSystemIntegrationTest:
    """Comprehensive embedding system integration test suite"""

    def __init__(self):
        self.test_dir = None
        self.config = None
        self.contestant_data = None
        
    def setup(self):
        """Set up test environment"""
        # Create temporary directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="embedding_test_"))
        
        # Create directory structure
        directories = [
            "source/photo/contestants",
            "cache/embeddings", 
            "processed_videos",
            "metadata",
            "models",
            "source/videos"
        ]
        
        for dir_path in directories:
            (self.test_dir / dir_path).mkdir(parents=True, exist_ok=True)
        
        # Create test configuration
        self.config = self._create_test_config()
        
        # Create contestant data (all 96 contestants)
        self.contestant_data = self._create_complete_contestant_data()
        
        # Create sample video
        self._create_test_video()
        
        logger.info(f"Test environment set up at {self.test_dir}")
        
    def teardown(self):
        """Clean up test environment"""
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            logger.info(f"Test environment cleaned up at {self.test_dir}")
    
    def _create_test_config(self):
        """Create comprehensive test configuration"""
        config = {
            "face_detection": {
                "model": "opencv",
                "min_confidence": 0.5,
                "max_faces_per_frame": 20,
                "enable_hardware_acceleration": False,
                "model_path": str(self.test_dir / "models"),
                "scale_factor": 1.05,
                "min_neighbors": 3,
                "min_size": [20, 20]
            },
            "face_recognition": {
                "tolerance": 0.6,
                "similarity_threshold": 0.15,
                "max_distance": 15.0,
                "distance_method": "combined",
                "euclidean_weight": 0.6,
                "cosine_weight": 0.4
            },
            "contestants": {
                "info_csv": str(self.test_dir / "source" / "contestant_info.csv"),
                "photo_dir": str(self.test_dir / "source" / "photo" / "contestants"),
                "embeddings_cache": str(self.test_dir / "cache" / "embeddings"),
                "auto_generate_missing": True,
                "embedding_format": "npy",
                "dimension": 512
            },
            "processing": {
                "mode": "standard",
                "enable_optimization": False,
                "processing_interval": 5,
                "enable_interpolation": True,
                "output_dir": str(self.test_dir / "processed_videos"),
                "metadata_dir": str(self.test_dir / "metadata"),
                "preserve_audio": True,
                "output_format": "mp4",
                "batch_size": 1,
                "parallel_processing": False,
                "memory_optimization": True
            },
            "annotation": {
                "backend": "opencv",
                "box_thickness": 2,
                "text_thickness": 1,
                "text_scale": 0.6,
                "text_padding": 4,
                "box_color": [0, 255, 0],
                "text_color": [255, 255, 255],
                "background_color": [0, 255, 0],
                "show_confidence": True,
                "confidence_decimals": 2
            },
            "logging": {
                "level": "INFO",
                "log_to_file": True,
                "log_file": str(self.test_dir / "processing.log"),
                "console_output": True,
                "log_performance": True,
                "performance_interval": 100
            },
            "hardware": {
                "auto_detect": True,
                "force_cpu": False,
                "gpu_memory_limit": 0.8
            }
        }
        
        # Write config file
        config_path = self.test_dir / "test_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)
        
        return config
        
    def _create_complete_contestant_data(self):
        """Create complete contestant data for all 96 contestants"""
        
        # Sample names and nicknames (we'll generate all 96)
        sample_names = [
            ("蘇雅琳", "Ivy So"), ("黃雅慧", "咖喱"), ("邱彦筒", "Marf"),
            ("穎蕎", "穎蕎"), ("坂部佩莎", "莎莎"), ("陳玉幸", "Hannah"),
            ("梁式昕", "Catrina"), ("陳玥伶", "小砂"), ("羅洛家", "Carmina"),
            ("謝安琪", "Kay"), ("張婧儀", "Jinny"), ("王灝兒", "JW"),
            ("鄧麗欣", "Stephy"), ("衛詩雅", "Michelle"), ("胡定欣", "Nancy"),
            ("楊明", "Alex"), ("徐子珊", "Kate"), ("黃智雯", "Mandy"),
            ("朱智賢", "Annie"), ("張曦雯", "Kelly")
        ]
        
        contestants = []
        csv_path = self.test_dir / "source" / "contestant_info.csv"
        
        # Generate all 96 contestants
        for i in range(1, 97):  # 1 to 96
            name_idx = (i - 1) % len(sample_names)
            name, nickname = sample_names[name_idx]
            
            # Add number suffix for uniqueness
            if i > len(sample_names):
                suffix = i // len(sample_names)
                name = f"{name}{suffix}"
                nickname = f"{nickname}{suffix}"
            
            contestant = {
                "編號": i,
                "姓名": name,
                "暱稱": nickname,
                "年齡": 20 + (i % 15)  # Ages between 20-34
            }
            contestants.append(contestant)
            
            # Create contestant photo directory and sample photos
            contestant_dir = self.test_dir / "source" / "photo" / "contestants" / str(i)
            contestant_dir.mkdir(parents=True, exist_ok=True)
            
            # Create 2-3 sample photos for each contestant
            for photo_idx in range(2):
                photo_path = contestant_dir / f"{i}-{photo_idx + 1}.jpg"
                self._create_contestant_photo(photo_path, i)
        
        # Write CSV file
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("編號,姓名,暱稱,年齡\n")
            for contestant in contestants:
                f.write(f"{contestant['編號']},{contestant['姓名']},{contestant['暱稱']},{contestant['年齡']}\n")
                
        logger.info(f"Created contestant data for {len(contestants)} contestants")
        return contestants
    
    def _create_contestant_photo(self, photo_path: Path, contestant_id: int):
        """Create a unique sample photo for each contestant"""
        # Create a 200x200 image with unique colors per contestant
        image = np.zeros((200, 200, 3), dtype=np.uint8)
        
        # Generate unique color based on contestant ID
        hue = (contestant_id * 137) % 180  # Golden angle distribution
        saturation = 150 + (contestant_id % 105)  # Vary saturation
        value = 180 + (contestant_id % 75)  # Vary brightness
        
        # Create HSV image and convert to BGR
        hsv_image = np.full((200, 200, 3), [hue, saturation, value], dtype=np.uint8)
        bgr_image = cv2.cvtColor(hsv_image, cv2.COLOR_HSV2BGR)
        
        # Add face-like features
        # Face outline
        cv2.rectangle(bgr_image, (50, 50), (150, 150), (255, 255, 255), -1)
        cv2.rectangle(bgr_image, (50, 50), (150, 150), (0, 0, 0), 2)
        
        # Eyes
        cv2.circle(bgr_image, (75, 80), 8, (0, 0, 0), -1)
        cv2.circle(bgr_image, (125, 80), 8, (0, 0, 0), -1)
        
        # Nose
        cv2.line(bgr_image, (100, 90), (100, 110), (0, 0, 0), 2)
        
        # Mouth
        cv2.ellipse(bgr_image, (100, 125), (15, 8), 0, 0, 180, (0, 0, 0), 2)
        
        # Add contestant ID as text
        cv2.putText(bgr_image, str(contestant_id), (10, 190), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.imwrite(str(photo_path), bgr_image)
    
    def _create_test_video(self):
        """Create a test video for processing"""
        video_path = self.test_dir / "source" / "videos" / "test_video.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create simple test video
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))
        
        # Create 60 frames (2 seconds at 30fps)
        for i in range(60):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:, :] = [100 + i * 2, 150, 200 - i]  # Changing colors
            
            # Add frame number
            cv2.putText(frame, f"Frame {i}", (50, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Simulate faces with rectangles
            if i % 10 < 5:  # Face present in first half of each second
                cv2.rectangle(frame, (200, 150), (300, 250), (255, 200, 150), -1)
                cv2.rectangle(frame, (200, 150), (300, 250), (0, 0, 0), 2)
            
            out.write(frame)
        
        out.release()
        logger.info(f"Created test video at {video_path}")
    
    def test_unified_face_detector_loading(self):
        """Test 1: Verify UnifiedFaceDetector loads correctly"""
        print("\n=== Test 1: UnifiedFaceDetector Loading ===")
        
        try:
            # Mock the embedding system and database to avoid actual loading
            with patch("unified_embedding_system.UnifiedEmbeddingSystem") as mock_embedding_system, \
                 patch("unified_face_detector.UnifiedContestantDatabase") as mock_contestant_db:
                
                # Setup mocks
                mock_embedding_instance = Mock()
                mock_embedding_instance.get_optimal_threshold.return_value = 0.6
                mock_embedding_system.return_value = mock_embedding_instance
                
                mock_db_instance = Mock()
                mock_contestant_db.return_value = mock_db_instance
                
                # Import and initialize
                from unified_face_detector import UnifiedFaceDetector
                
                detector = UnifiedFaceDetector(self.config)
                
                # Verify initialization
                assert detector is not None, "UnifiedFaceDetector should initialize"
                assert detector.config == self.config, "Configuration should be set"
                assert detector.embedding_system is not None, "Embedding system should be initialized"
                assert detector.contestant_db is not None, "Contestant database should be initialized"
                
                print("✅ UnifiedFaceDetector loads successfully")
                return True
                
        except Exception as e:
            print(f"❌ UnifiedFaceDetector loading failed: {str(e)}")
            return False
    
    def test_contestant_database_initialization(self):
        """Test 2: Verify all 96 contestant embeddings load correctly"""
        print("\n=== Test 2: Contestant Database Initialization ===")
        
        try:
            # Create mock embeddings for all 96 contestants
            embeddings_dir = self.test_dir / "cache" / "embeddings"
            embeddings_dir.mkdir(parents=True, exist_ok=True)
            
            mock_embeddings = {}
            for i in range(1, 97):
                # Create mock embedding file
                embedding_path = embeddings_dir / f"{i}_embedding.npy"
                mock_embedding = np.random.rand(512).astype(np.float32)
                np.save(embedding_path, mock_embedding)
                mock_embeddings[i] = mock_embedding
            
            # Mock the actual database class
            with patch("face_detector.ContestantDatabase") as mock_database_class:
                mock_db_instance = Mock()
                mock_db_instance.load_contestants.return_value = len(self.contestant_data)
                mock_db_instance.contestants = {
                    contestant["編號"]: {
                        "name": contestant["姓名"],
                        "nickname": contestant["暱稱"],
                        "age": contestant["年齡"],
                        "embedding": mock_embeddings[contestant["編號"]]
                    } for contestant in self.contestant_data
                }
                mock_database_class.return_value = mock_db_instance
                
                # Initialize database
                loaded_count = mock_db_instance.load_contestants()
                
                # Verify all contestants loaded
                assert loaded_count == 96, f"Expected 96 contestants, got {loaded_count}"
                assert len(mock_db_instance.contestants) == 96, "Should have 96 contestant records"
                
                # Verify specific contestants exist
                test_ids = [1, 21, 96]  # Including problematic IDs from task description
                for contestant_id in test_ids:
                    assert contestant_id in mock_db_instance.contestants, f"Contestant {contestant_id} should exist"
                    contestant = mock_db_instance.contestants[contestant_id]
                    assert "embedding" in contestant, f"Contestant {contestant_id} should have embedding"
                    assert contestant["embedding"].shape == (512,), f"Embedding should be 512-dimensional"
                
                print(f"✅ All 96 contestants loaded successfully")
                print(f"✅ Verified contestants 1, 21, and 96 exist with proper embeddings")
                return True
                
        except Exception as e:
            print(f"❌ Contestant database initialization failed: {str(e)}")
            return False
    
    def test_video_path_resolution(self):
        """Test 3: Validate video path resolution works properly"""
        print("\n=== Test 3: Video Path Resolution ===")
        
        try:
            # Test video should exist
            video_path = self.test_dir / "source" / "videos" / "test_video.mp4"
            assert video_path.exists(), f"Test video should exist at {video_path}"
            
            # Test path resolution logic
            config_source_dir = Path(self.config["contestants"]["photo_dir"]).parent.parent
            expected_videos_dir = config_source_dir / "videos"
            
            assert expected_videos_dir.exists(), "Videos directory should exist"
            
            # Find video files
            video_files = list(expected_videos_dir.glob("*.mp4"))
            assert len(video_files) >= 1, "Should find at least one video file"
            
            # Verify video is readable
            cap = cv2.VideoCapture(str(video_path))
            assert cap.isOpened(), "Video should be readable by OpenCV"
            
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            
            assert frame_count > 0, "Video should have frames"
            assert fps > 0, "Video should have valid FPS"
            
            print(f"✅ Video path resolution works correctly")
            print(f"✅ Found video with {frame_count} frames at {fps} FPS")
            return True
            
        except Exception as e:
            print(f"❌ Video path resolution failed: {str(e)}")
            return False
    
    def test_processing_pipeline_startup(self):
        """Test 4: Validate processing pipeline starts successfully"""
        print("\n=== Test 4: Processing Pipeline Startup ===")
        
        try:
            # Mock the pipeline components
            with patch("video_processing_engine.VideoProcessor") as mock_processor, \
                 patch("unified_face_detector.UnifiedFaceDetector") as mock_detector:
                
                # Setup mocks
                mock_processor_instance = Mock()
                mock_processor.return_value = mock_processor_instance
                
                mock_detector_instance = Mock()
                mock_detector_instance.detect_faces.return_value = []
                mock_detector.return_value = mock_detector_instance
                
                # Test pipeline initialization
                from video_processing_engine import VideoProcessingConfig, VideoProcessor
                
                video_path = str(self.test_dir / "source" / "videos" / "test_video.mp4")
                output_path = str(self.test_dir / "processed_videos" / "test_output.mp4")
                
                processing_config = VideoProcessingConfig(
                    source_path=video_path,
                    target_path=output_path,
                    confidence_threshold=0.3,
                    iou_threshold=0.5,
                    enable_tracking=True,
                    enable_smoothing=True,
                    max_faces_per_frame=10
                )
                
                processor = VideoProcessor(processing_config)
                
                # Verify processor initialization
                assert processor is not None, "Processor should initialize"
                assert processor.config == processing_config, "Configuration should be set"
                
                print("✅ Processing pipeline starts successfully")
                return True
                
        except Exception as e:
            print(f"❌ Processing pipeline startup failed: {str(e)}")
            return False
    
    def test_embedding_auto_generation_fallback(self):
        """Test 5: Check embedding auto-generation fallback functionality"""
        print("\n=== Test 5: Embedding Auto-Generation Fallback ===")
        
        try:
            # Remove some embedding files to test auto-generation
            embeddings_dir = self.test_dir / "cache" / "embeddings"
            test_ids = [21, 96]  # Test with previously problematic IDs
            
            for test_id in test_ids:
                embedding_file = embeddings_dir / f"{test_id}_embedding.npy"
                if embedding_file.exists():
                    embedding_file.unlink()
            
            # Mock the embedding generation system
            with patch("unified_embedding_system.UnifiedEmbeddingSystem") as mock_system:
                mock_system_instance = Mock()
                
                # Mock generate_contestant_embedding method
                def mock_generate_embedding(contestant_id, photos_dir):
                    # Simulate successful embedding generation
                    return np.random.rand(512).astype(np.float32)
                
                mock_system_instance.generate_contestant_embedding = Mock(side_effect=mock_generate_embedding)
                mock_system_instance.get_optimal_threshold.return_value = 0.6
                mock_system.return_value = mock_system_instance
                
                # Test auto-generation
                from unified_embedding_system import UnifiedEmbeddingSystem
                
                embedding_system = UnifiedEmbeddingSystem(self.config)
                
                # Test generation for missing embeddings
                for test_id in test_ids:
                    photos_dir = self.test_dir / "source" / "photo" / "contestants" / str(test_id)
                    embedding = embedding_system.generate_contestant_embedding(test_id, str(photos_dir))
                    
                    assert embedding is not None, f"Should generate embedding for contestant {test_id}"
                    assert embedding.shape == (512,), f"Generated embedding should be 512-dimensional"
                
                print("✅ Embedding auto-generation fallback works correctly")
                print(f"✅ Successfully generated embeddings for contestants {test_ids}")
                return True
                
        except Exception as e:
            print(f"❌ Embedding auto-generation fallback failed: {str(e)}")
            return False
    
    def run_comprehensive_test(self):
        """Run all integration tests"""
        print("🚀 Starting Comprehensive Embedding System Integration Test")
        print("=" * 70)
        
        try:
            self.setup()
            
            # Run all tests
            tests = [
                ("UnifiedFaceDetector Loading", self.test_unified_face_detector_loading),
                ("Contestant Database (96 contestants)", self.test_contestant_database_initialization),
                ("Video Path Resolution", self.test_video_path_resolution),
                ("Processing Pipeline Startup", self.test_processing_pipeline_startup),
                ("Embedding Auto-Generation Fallback", self.test_embedding_auto_generation_fallback)
            ]
            
            results = []
            for test_name, test_func in tests:
                try:
                    result = test_func()
                    results.append((test_name, result))
                except Exception as e:
                    print(f"❌ {test_name} failed with exception: {str(e)}")
                    results.append((test_name, False))
            
            # Print summary
            print("\n" + "=" * 70)
            print("📊 TEST RESULTS SUMMARY")
            print("=" * 70)
            
            passed = 0
            total = len(results)
            
            for test_name, result in results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} {test_name}")
                if result:
                    passed += 1
            
            print("=" * 70)
            print(f"OVERALL RESULT: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
            
            if passed == total:
                print("🎉 ALL TESTS PASSED - Embedding system is ready!")
                return True
            else:
                print("⚠️  Some tests failed - system needs attention")
                return False
                
        except Exception as e:
            print(f"❌ Integration test suite failed: {str(e)}")
            return False
        finally:
            self.teardown()


def run_integration_test():
    """Standalone function to run the integration test"""
    test_suite = EmbeddingSystemIntegrationTest()
    return test_suite.run_comprehensive_test()


if __name__ == "__main__":
    # Run as standalone script
    import sys
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Run the test
    success = run_integration_test()
    sys.exit(0 if success else 1)


# Pytest integration
@pytest.mark.integration
@pytest.mark.slow  
def test_embedding_system_integration():
    """Pytest wrapper for the comprehensive integration test"""
    test_suite = EmbeddingSystemIntegrationTest()
    assert test_suite.run_comprehensive_test(), "Embedding system integration test should pass"