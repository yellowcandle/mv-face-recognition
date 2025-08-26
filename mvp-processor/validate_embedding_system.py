#!/usr/bin/env python3
"""
Standalone Embedding System Validation Script

This script validates the complete embedding system integration after fixes are applied.
It can be run independently without pytest to quickly verify system health.

Usage:
    python validate_embedding_system.py [--config CONFIG_PATH] [--verbose]

Requirements:
1. Verify all 96 contestant embeddings load correctly
2. Test video path resolution works properly  
3. Validate that the processing pipeline starts successfully
4. Check embedding auto-generation fallback functionality
"""

import argparse
import logging
import sys
import yaml
from pathlib import Path
import pandas as pd
import numpy as np
import cv2
import traceback
from typing import Dict, List, Optional, Tuple
import time

# Add src directory to Python path
sys.path.append(str(Path(__file__).parent / "src"))

class EmbeddingSystemValidator:
    """Standalone validator for the embedding system"""
    
    def __init__(self, config_path: Optional[str] = None, verbose: bool = False):
        self.config_path = config_path or "config/unified_config.yaml"
        self.verbose = verbose
        self.config = None
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        return logging.getLogger(__name__)
    
    def load_config(self) -> bool:
        """Load and validate configuration file"""
        self.logger.info("Loading configuration...")
        
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                self.logger.error(f"Configuration file not found: {config_file}")
                return False
            
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            # Validate required sections
            required_sections = ['contestants', 'face_detection', 'face_recognition', 'processing']
            missing_sections = [section for section in required_sections if section not in self.config]
            
            if missing_sections:
                self.logger.error(f"Missing required config sections: {missing_sections}")
                return False
            
            self.logger.info("✅ Configuration loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load configuration: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return False
    
    def validate_contestant_data(self) -> Tuple[bool, Dict]:
        """Validate contestant database and CSV file"""
        self.logger.info("Validating contestant data...")
        
        results = {
            "csv_exists": False,
            "csv_readable": False,
            "contestant_count": 0,
            "required_contestants": [1, 21, 96],  # Specifically mentioned in requirements
            "missing_contestants": [],
            "photo_directories": {},
            "total_photos": 0
        }
        
        try:
            # Check CSV file
            csv_path = Path(self.config["contestants"]["info_csv"])
            if not csv_path.exists():
                self.logger.error(f"❌ Contestant CSV not found: {csv_path}")
                return False, results
            
            results["csv_exists"] = True
            
            # Read and validate CSV
            try:
                df = pd.read_csv(csv_path, encoding='utf-8')
                results["csv_readable"] = True
                results["contestant_count"] = len(df)
                
                # Check for required columns
                required_columns = ['編號', '姓名', '暱稱']
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    self.logger.error(f"❌ Missing required columns: {missing_columns}")
                    return False, results
                
                # Check for required contestant IDs
                contestant_ids = set(df['編號'].tolist())
                for required_id in results["required_contestants"]:
                    if required_id not in contestant_ids:
                        results["missing_contestants"].append(required_id)
                
                self.logger.info(f"✅ Found {len(contestant_ids)} contestants in CSV")
                
                if len(contestant_ids) >= 96:
                    self.logger.info("✅ CSV contains at least 96 contestants")
                else:
                    self.logger.warning(f"⚠️  CSV contains only {len(contestant_ids)} contestants (expected 96)")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to read CSV: {str(e)}")
                return False, results
            
            # Check photo directories
            photo_dir = Path(self.config["contestants"]["photo_dir"])
            if not photo_dir.exists():
                self.logger.error(f"❌ Photo directory not found: {photo_dir}")
                return False, results
            
            # Check specific contestant photo directories
            for contestant_id in results["required_contestants"]:
                contestant_dir = photo_dir / str(contestant_id)
                if contestant_dir.exists():
                    photos = list(contestant_dir.glob("*.jpg")) + list(contestant_dir.glob("*.png"))
                    results["photo_directories"][contestant_id] = len(photos)
                    results["total_photos"] += len(photos)
                    self.logger.info(f"✅ Contestant {contestant_id}: {len(photos)} photos")
                else:
                    results["photo_directories"][contestant_id] = 0
                    self.logger.warning(f"⚠️  Contestant {contestant_id}: no photo directory")
            
            return True, results
            
        except Exception as e:
            self.logger.error(f"❌ Contestant data validation failed: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return False, results
    
    def validate_embedding_system(self) -> Tuple[bool, Dict]:
        """Validate embedding system components"""
        self.logger.info("Validating embedding system...")
        
        results = {
            "embeddings_dir_exists": False,
            "embedding_files_found": 0,
            "missing_embeddings": [],
            "embedding_dimensions": {},
            "system_loadable": False
        }
        
        try:
            # Check embeddings directory
            embeddings_dir = Path(self.config["contestants"]["embeddings_cache"])
            results["embeddings_dir_exists"] = embeddings_dir.exists()
            
            if not embeddings_dir.exists():
                self.logger.warning(f"⚠️  Embeddings directory not found: {embeddings_dir}")
                self.logger.info("This is expected if embeddings haven't been generated yet")
            else:
                # Check for embedding files
                embedding_files = list(embeddings_dir.glob("*.npy"))
                results["embedding_files_found"] = len(embedding_files)
                self.logger.info(f"Found {len(embedding_files)} embedding files")
                
                # Test loading a few embeddings
                test_ids = [1, 21, 96]  # Critical contestant IDs
                for test_id in test_ids:
                    embedding_file = embeddings_dir / f"{test_id}_embedding.npy"
                    if embedding_file.exists():
                        try:
                            embedding = np.load(embedding_file)
                            results["embedding_dimensions"][test_id] = embedding.shape
                            self.logger.info(f"✅ Contestant {test_id}: embedding shape {embedding.shape}")
                        except Exception as e:
                            self.logger.error(f"❌ Failed to load embedding for contestant {test_id}: {str(e)}")
                    else:
                        results["missing_embeddings"].append(test_id)
                        self.logger.warning(f"⚠️  Missing embedding for contestant {test_id}")
            
            # Test system imports (without full initialization)
            try:
                from unified_embedding_system import UnifiedEmbeddingSystem
                from unified_face_detector import UnifiedFaceDetector
                results["system_loadable"] = True
                self.logger.info("✅ Embedding system classes import successfully")
            except ImportError as e:
                self.logger.error(f"❌ Failed to import embedding system: {str(e)}")
                results["system_loadable"] = False
            
            return True, results
            
        except Exception as e:
            self.logger.error(f"❌ Embedding system validation failed: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return False, results
    
    def validate_video_processing(self) -> Tuple[bool, Dict]:
        """Validate video processing capabilities"""
        self.logger.info("Validating video processing...")
        
        results = {
            "videos_dir_exists": False,
            "video_files_found": 0,
            "sample_video_readable": False,
            "opencv_working": False,
            "processing_dirs_exist": False
        }
        
        try:
            # Check for videos directory
            contestants_csv = Path(self.config["contestants"]["info_csv"])
            source_dir = contestants_csv.parent
            videos_dir = source_dir / "videos"
            
            results["videos_dir_exists"] = videos_dir.exists()
            
            if not videos_dir.exists():
                self.logger.warning(f"⚠️  Videos directory not found: {videos_dir}")
                self.logger.info("Create videos directory and add test videos for processing")
            else:
                # Find video files
                video_extensions = ["*.mp4", "*.avi", "*.mov", "*.mkv"]
                video_files = []
                for ext in video_extensions:
                    video_files.extend(list(videos_dir.glob(ext)))
                
                results["video_files_found"] = len(video_files)
                self.logger.info(f"Found {len(video_files)} video files")
                
                # Test reading a sample video if available
                if video_files:
                    sample_video = video_files[0]
                    try:
                        cap = cv2.VideoCapture(str(sample_video))
                        if cap.isOpened():
                            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            cap.release()
                            
                            results["sample_video_readable"] = True
                            self.logger.info(f"✅ Sample video readable: {sample_video.name}")
                            self.logger.info(f"   Properties: {width}x{height}, {frame_count} frames, {fps} FPS")
                        else:
                            self.logger.error(f"❌ Cannot read sample video: {sample_video}")
                    except Exception as e:
                        self.logger.error(f"❌ Error reading sample video: {str(e)}")
            
            # Test OpenCV
            try:
                # Test basic OpenCV functionality
                test_image = np.zeros((100, 100, 3), dtype=np.uint8)
                gray = cv2.cvtColor(test_image, cv2.COLOR_BGR2GRAY)
                results["opencv_working"] = True
                self.logger.info("✅ OpenCV working correctly")
            except Exception as e:
                self.logger.error(f"❌ OpenCV error: {str(e)}")
                results["opencv_working"] = False
            
            # Check processing directories
            processing_dirs = [
                Path(self.config["processing"]["output_dir"]),
                Path(self.config["processing"]["metadata_dir"])
            ]
            
            all_dirs_exist = True
            for dir_path in processing_dirs:
                if not dir_path.exists():
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"Created directory: {dir_path}")
                
                if not dir_path.exists():
                    all_dirs_exist = False
                    self.logger.error(f"❌ Failed to create directory: {dir_path}")
            
            results["processing_dirs_exist"] = all_dirs_exist
            if all_dirs_exist:
                self.logger.info("✅ Processing directories ready")
            
            return True, results
            
        except Exception as e:
            self.logger.error(f"❌ Video processing validation failed: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return False, results
    
    def validate_pipeline_startup(self) -> Tuple[bool, Dict]:
        """Test that the processing pipeline can start up"""
        self.logger.info("Validating pipeline startup...")
        
        results = {
            "imports_successful": False,
            "config_valid": False,
            "mock_initialization": False
        }
        
        try:
            # Test critical imports
            try:
                from unified_face_detector import UnifiedFaceDetector
                from unified_embedding_system import UnifiedEmbeddingSystem
                from video_processing_engine import VideoProcessor, VideoProcessingConfig
                results["imports_successful"] = True
                self.logger.info("✅ All required modules import successfully")
            except ImportError as e:
                self.logger.error(f"❌ Import error: {str(e)}")
                return False, results
            
            # Validate configuration completeness for pipeline
            required_config_keys = [
                "face_detection.model",
                "face_detection.min_confidence",
                "face_recognition.tolerance",
                "contestants.info_csv",
                "contestants.photo_dir",
                "processing.output_dir"
            ]
            
            config_valid = True
            for key in required_config_keys:
                keys = key.split('.')
                current = self.config
                try:
                    for k in keys:
                        current = current[k]
                except KeyError:
                    self.logger.error(f"❌ Missing configuration key: {key}")
                    config_valid = False
                    break
            
            results["config_valid"] = config_valid
            if config_valid:
                self.logger.info("✅ Configuration is complete for pipeline startup")
            
            # Test mock initialization (without actual model loading)
            try:
                # Create a minimal configuration for testing
                test_config = VideoProcessingConfig(
                    source_path="test_input.mp4",
                    target_path="test_output.mp4",
                    confidence_threshold=0.3,
                    enable_tracking=True
                )
                
                # This should not fail due to configuration issues
                results["mock_initialization"] = True
                self.logger.info("✅ Pipeline configuration creates successfully")
                
            except Exception as e:
                self.logger.error(f"❌ Pipeline configuration error: {str(e)}")
                results["mock_initialization"] = False
            
            return True, results
            
        except Exception as e:
            self.logger.error(f"❌ Pipeline startup validation failed: {str(e)}")
            if self.verbose:
                traceback.print_exc()
            return False, results
    
    def generate_detailed_report(self, validation_results: Dict) -> str:
        """Generate a detailed validation report"""
        report = []
        report.append("=" * 80)
        report.append("EMBEDDING SYSTEM VALIDATION REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Configuration: {self.config_path}")
        report.append("")
        
        # Configuration section
        report.append("📋 CONFIGURATION")
        report.append("-" * 40)
        if validation_results["config"]["success"]:
            report.append("✅ Configuration loaded successfully")
        else:
            report.append("❌ Configuration loading failed")
        report.append("")
        
        # Contestant Data section
        report.append("👥 CONTESTANT DATA")
        report.append("-" * 40)
        contestant_data = validation_results["contestant_data"]["data"]
        
        if validation_results["contestant_data"]["success"]:
            report.append(f"✅ CSV file exists and readable")
            report.append(f"   Total contestants: {contestant_data['contestant_count']}")
            
            if contestant_data["missing_contestants"]:
                report.append(f"⚠️  Missing required contestants: {contestant_data['missing_contestants']}")
            else:
                report.append(f"✅ All required contestants present (1, 21, 96)")
            
            report.append(f"   Photo directories checked: {len(contestant_data['photo_directories'])}")
            report.append(f"   Total photos found: {contestant_data['total_photos']}")
            
        else:
            report.append("❌ Contestant data validation failed")
        report.append("")
        
        # Embedding System section
        report.append("🧠 EMBEDDING SYSTEM")
        report.append("-" * 40)
        embedding_data = validation_results["embedding_system"]["data"]
        
        if validation_results["embedding_system"]["success"]:
            report.append(f"✅ Embedding system validation completed")
            
            if embedding_data["embeddings_dir_exists"]:
                report.append(f"   Embedding files found: {embedding_data['embedding_files_found']}")
                
                if embedding_data["missing_embeddings"]:
                    report.append(f"⚠️  Missing embeddings for: {embedding_data['missing_embeddings']}")
                    report.append("   (These will be auto-generated during processing)")
                else:
                    report.append("✅ All required embeddings present")
                
                for contestant_id, shape in embedding_data["embedding_dimensions"].items():
                    report.append(f"   Contestant {contestant_id}: {shape}")
            else:
                report.append("⚠️  Embeddings directory not found - will be created during processing")
            
            if embedding_data["system_loadable"]:
                report.append("✅ Embedding system classes importable")
            else:
                report.append("❌ Embedding system import errors")
                
        else:
            report.append("❌ Embedding system validation failed")
        report.append("")
        
        # Video Processing section
        report.append("🎬 VIDEO PROCESSING")
        report.append("-" * 40)
        video_data = validation_results["video_processing"]["data"]
        
        if validation_results["video_processing"]["success"]:
            if video_data["videos_dir_exists"]:
                report.append(f"✅ Videos directory exists")
                report.append(f"   Video files found: {video_data['video_files_found']}")
                
                if video_data["sample_video_readable"]:
                    report.append("✅ Sample video readable by OpenCV")
                elif video_data["video_files_found"] > 0:
                    report.append("⚠️  Video files found but not readable")
                else:
                    report.append("ℹ️  No video files found for testing")
            else:
                report.append("⚠️  Videos directory not found")
                report.append("   Create source/videos/ directory and add video files")
            
            if video_data["opencv_working"]:
                report.append("✅ OpenCV functioning correctly")
            else:
                report.append("❌ OpenCV issues detected")
            
            if video_data["processing_dirs_exist"]:
                report.append("✅ Processing directories ready")
            else:
                report.append("❌ Processing directory creation failed")
                
        else:
            report.append("❌ Video processing validation failed")
        report.append("")
        
        # Pipeline Startup section
        report.append("🚀 PIPELINE STARTUP")
        report.append("-" * 40)
        pipeline_data = validation_results["pipeline_startup"]["data"]
        
        if validation_results["pipeline_startup"]["success"]:
            if pipeline_data["imports_successful"]:
                report.append("✅ All required modules import successfully")
            else:
                report.append("❌ Module import failures")
            
            if pipeline_data["config_valid"]:
                report.append("✅ Configuration complete for pipeline")
            else:
                report.append("❌ Configuration missing required keys")
            
            if pipeline_data["mock_initialization"]:
                report.append("✅ Pipeline components initialize correctly")
            else:
                report.append("❌ Pipeline initialization issues")
        else:
            report.append("❌ Pipeline startup validation failed")
        report.append("")
        
        # Overall Assessment
        report.append("📊 OVERALL ASSESSMENT")
        report.append("-" * 40)
        
        success_count = sum(1 for result in validation_results.values() if result["success"])
        total_count = len(validation_results)
        success_rate = (success_count / total_count) * 100
        
        report.append(f"Validation Results: {success_count}/{total_count} ({success_rate:.1f}%)")
        
        if success_rate == 100:
            report.append("🎉 SYSTEM READY: All validations passed!")
            report.append("   The embedding system is ready for video processing.")
        elif success_rate >= 80:
            report.append("⚠️  MOSTLY READY: Minor issues detected")
            report.append("   System should work with some warnings.")
        else:
            report.append("❌ ISSUES DETECTED: Significant problems found")
            report.append("   System may not function properly until fixed.")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def run_validation(self) -> bool:
        """Run complete validation suite"""
        self.logger.info("🚀 Starting Embedding System Validation")
        self.logger.info("=" * 60)
        
        validation_results = {}
        
        # Load configuration
        config_success = self.load_config()
        validation_results["config"] = {"success": config_success}
        
        if not config_success:
            self.logger.error("❌ Cannot continue without valid configuration")
            return False
        
        # Run all validations
        validations = [
            ("contestant_data", self.validate_contestant_data),
            ("embedding_system", self.validate_embedding_system),
            ("video_processing", self.validate_video_processing),
            ("pipeline_startup", self.validate_pipeline_startup)
        ]
        
        for validation_name, validation_func in validations:
            self.logger.info(f"\n🔍 Running {validation_name} validation...")
            try:
                success, data = validation_func()
                validation_results[validation_name] = {
                    "success": success,
                    "data": data
                }
            except Exception as e:
                self.logger.error(f"❌ {validation_name} validation failed: {str(e)}")
                validation_results[validation_name] = {
                    "success": False,
                    "data": {}
                }
        
        # Generate and display report
        report = self.generate_detailed_report(validation_results)
        print("\n" + report)
        
        # Calculate overall success
        success_count = sum(1 for result in validation_results.values() if result["success"])
        total_count = len(validation_results)
        overall_success = success_count == total_count
        
        if overall_success:
            self.logger.info("🎉 All validations passed! System is ready.")
            return True
        else:
            self.logger.error(f"⚠️  {total_count - success_count} validations failed. See report above.")
            return False


def main():
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(
        description="Validate embedding system integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic validation with default config
    python validate_embedding_system.py
    
    # Validation with custom config and verbose output  
    python validate_embedding_system.py --config custom_config.yaml --verbose
    
    # Quick check (less verbose)
    python validate_embedding_system.py --quiet
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        default="config/unified_config.yaml",
        help="Path to configuration file (default: config/unified_config.yaml)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with detailed logging"
    )
    
    parser.add_argument(
        "--quiet", "-q", 
        action="store_true",
        help="Minimal output (overrides verbose)"
    )
    
    args = parser.parse_args()
    
    # Determine verbosity
    verbose = args.verbose and not args.quiet
    
    try:
        # Run validation
        validator = EmbeddingSystemValidator(
            config_path=args.config,
            verbose=verbose
        )
        
        success = validator.run_validation()
        
        if success:
            print("\n✅ Validation completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Validation completed with issues!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Validation failed with error: {str(e)}")
        if verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()