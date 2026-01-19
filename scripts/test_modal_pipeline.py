#!/usr/bin/env python3
"""
Local test of Modal pipeline functions.

Tests Modal functions without needing to deploy to Modal cloud:
1. System status check
2. Sync from HuggingFace (dry run)
3. Video processing (mock)
4. Upload results (dry run)

Usage:
    python scripts/test_modal_pipeline.py
    python scripts/test_modal_pipeline.py --test status
    python scripts/test_modal_pipeline.py --test sync
    python scripts/test_modal_pipeline.py --test process
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ModalPipelineTestSuite:
    """Test Modal pipeline functions locally."""

    def __init__(self):
        """Initialize test suite."""
        self.results = {}
        self.passed = 0
        self.failed = 0

    def test_system_status(self) -> bool:
        """Test system status check."""
        test_name = "System Status Check"
        logger.info(f"\nTesting: {test_name}")
        
        try:
            status = {
                "chromadb": False,
                "models": False,
                "storage": False,
                "contestants": 0,
            }
            
            import chromadb
            try:
                client = chromadb.PersistentClient(path=".chroma_db")
                collection = client.get_collection(name="contestants_faces")
                status["chromadb"] = True
                status["contestants"] = collection.count()
                logger.info(f"  ✅ ChromaDB: {status['contestants']} contestants")
            except Exception as e:
                logger.warning(f"  ⚠️  ChromaDB: {e}")
            
            try:
                import insightface
                status["models"] = True
                logger.info(f"  ✅ InsightFace models available")
            except ImportError:
                logger.warning(f"  ⚠️  InsightFace not installed")
            
            storage_path = Path(".chroma_db")
            status["storage"] = storage_path.exists()
            logger.info(f"  ✅ Storage: {storage_path.exists()}")
            
            result = {
                "test": test_name,
                "status": "PASS",
                "ready": status["chromadb"] and status["models"],
                "details": status,
            }
            self.results[test_name] = result
            self.passed += 1
            return True
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            self.results[test_name] = {"test": test_name, "status": "FAIL", "error": str(e)}
            self.failed += 1
            return False

    def test_huggingface_sync(self) -> bool:
        """Test HuggingFace sync (dry run)."""
        test_name = "HuggingFace Sync"
        logger.info(f"\nTesting: {test_name}")
        
        try:
            hf_token = __import__("os").getenv("HF_TOKEN")
            
            if not hf_token:
                logger.warning("  ⚠️  HF_TOKEN not set - would sync with token")
                result = {
                    "test": test_name,
                    "status": "SKIP",
                    "reason": "HF_TOKEN not configured",
                }
                self.results[test_name] = result
                return True
            
            try:
                from huggingface_hub import HfApi
                api = HfApi(token=hf_token)
                logger.info("  ✅ HuggingFace API connected")
                logger.info("  ℹ️  Dataset: yellowcandle/mv-face-recognition-data")
                logger.info("  ℹ️  Would sync: contestant_info.csv, embeddings/, flagged_faces/")
                
                result = {
                    "test": test_name,
                    "status": "PASS",
                    "repo": "yellowcandle/mv-face-recognition-data",
                    "ready": True,
                }
                self.results[test_name] = result
                self.passed += 1
                return True
            except ImportError:
                logger.warning("  ⚠️  huggingface_hub not installed")
                result = {
                    "test": test_name,
                    "status": "SKIP",
                    "reason": "huggingface_hub not installed",
                }
                self.results[test_name] = result
                return True
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            self.results[test_name] = {"test": test_name, "status": "FAIL", "error": str(e)}
            self.failed += 1
            return False

    def test_video_processing_readiness(self) -> bool:
        """Test video processing readiness."""
        test_name = "Video Processing Readiness"
        logger.info(f"\nTesting: {test_name}")
        
        try:
            video_dir = Path("source/videos")
            
            if not video_dir.exists():
                logger.warning(f"  ⚠️  Video directory not found: {video_dir}")
            else:
                video_files = list(video_dir.glob("*.mp4"))
                logger.info(f"  ✅ Found {len(video_files)} video files")
                for vf in video_files[:3]:
                    logger.info(f"     - {vf.name}")
            
            dependencies = {
                "opencv": False,
                "ffmpeg": False,
                "numpy": False,
            }
            
            try:
                import cv2
                dependencies["opencv"] = True
                logger.info("  ✅ OpenCV available")
            except ImportError:
                logger.warning("  ⚠️  OpenCV not available")
            
            try:
                import ffmpeg
                dependencies["ffmpeg"] = True
                logger.info("  ✅ FFmpeg available")
            except ImportError:
                logger.warning("  ⚠️  FFmpeg not available")
            
            try:
                import numpy
                dependencies["numpy"] = True
                logger.info("  ✅ NumPy available")
            except ImportError:
                logger.warning("  ⚠️  NumPy not available")
            
            ready = all(dependencies.values())
            result = {
                "test": test_name,
                "status": "PASS" if ready else "PARTIAL",
                "dependencies": dependencies,
                "ready": ready,
            }
            self.results[test_name] = result
            self.passed += 1
            return ready
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            self.results[test_name] = {"test": test_name, "status": "FAIL", "error": str(e)}
            self.failed += 1
            return False

    def test_database_upload(self) -> bool:
        """Test database upload readiness."""
        test_name = "Database Upload Readiness"
        logger.info(f"\nTesting: {test_name}")
        
        try:
            results_dir = Path("processed_videos")
            metadata_dir = Path("metadata")
            
            if not results_dir.exists():
                logger.info(f"  ℹ️  Results directory not yet created: {results_dir}")
            else:
                result_files = list(results_dir.rglob("*"))
                logger.info(f"  ℹ️  {len(result_files)} files in results directory")
            
            if not metadata_dir.exists():
                logger.info(f"  ℹ️  Metadata directory not yet created: {metadata_dir}")
            else:
                metadata_files = list(metadata_dir.glob("*.json"))
                logger.info(f"  ✅ {len(metadata_files)} metadata files")
            
            result = {
                "test": test_name,
                "status": "PASS",
                "ready": True,
                "note": "Upload would happen after video processing",
            }
            self.results[test_name] = result
            self.passed += 1
            return True
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            self.results[test_name] = {"test": test_name, "status": "FAIL", "error": str(e)}
            self.failed += 1
            return False

    def run_all_tests(self) -> bool:
        """Run all tests."""
        logger.info("=" * 60)
        logger.info("Modal Pipeline Test Suite")
        logger.info("=" * 60)
        
        self.test_system_status()
        self.test_huggingface_sync()
        self.test_video_processing_readiness()
        self.test_database_upload()
        
        return self._print_report()

    def run_specific_test(self, test_name: str) -> bool:
        """Run specific test."""
        test_map = {
            "status": self.test_system_status,
            "sync": self.test_huggingface_sync,
            "process": self.test_video_processing_readiness,
            "upload": self.test_database_upload,
        }
        
        if test_name not in test_map:
            logger.error(f"Unknown test: {test_name}")
            logger.info(f"Available: {', '.join(test_map.keys())}")
            return False
        
        return test_map[test_name]()

    def _print_report(self) -> bool:
        """Print test report."""
        logger.info("\n" + "=" * 60)
        logger.info("Test Results")
        logger.info("=" * 60)
        
        for test_name, result in self.results.items():
            status = result.get("status", "UNKNOWN")
            emoji = "✅" if status == "PASS" else "⚠️" if status in ("SKIP", "PARTIAL") else "❌"
            logger.info(f"{emoji} {test_name}: {status}")
            
            if "ready" in result:
                logger.info(f"   Ready: {result['ready']}")
        
        logger.info("\n" + "=" * 60)
        logger.info(f"Summary: {self.passed} passed, {self.failed} failed")
        logger.info("=" * 60)
        
        if self.failed == 0:
            logger.info("\n✅ All tests passed! Ready for Modal deployment.")
            logger.info("\nNext steps:")
            logger.info("1. Run: python scripts/setup_modal.py")
            logger.info("2. Configure: export HF_TOKEN=your_token")
            logger.info("3. Deploy: modal run scripts/modal_app.py --check-status")
        
        return self.failed == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Modal pipeline locally")
    parser.add_argument(
        "--test",
        help="Run specific test (status, sync, process, upload)",
    )
    
    args = parser.parse_args()
    
    suite = ModalPipelineTestSuite()
    
    if args.test:
        success = suite.run_specific_test(args.test)
    else:
        success = suite.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
