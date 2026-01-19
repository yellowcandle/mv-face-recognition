#!/usr/bin/env python3
"""
Test backend health endpoints locally.

Tests:
1. Root endpoint (/)
2. Health check (/health)
3. System status (/api/system/status/)
4. Videos endpoint (/api/videos/)
5. Contestants endpoint (/api/contestants/)
6. Database initialization verification

Usage:
    python scripts/test_backend_health.py
    python scripts/test_backend_health.py --url http://localhost:8000
    python scripts/test_backend_health.py --test videos
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    import requests
except ImportError:
    print("❌ requests library not found. Install with: pip install requests")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class BackendHealthTester:
    """Test backend health endpoints."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize tester."""
        self.base_url = base_url
        self.results = {}
        self.passed = 0
        self.failed = 0

    def is_backend_running(self) -> bool:
        """Check if backend is running."""
        try:
            response = requests.get(f"{self.base_url}/", timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def test_root_endpoint(self) -> bool:
        """Test root endpoint."""
        test_name = "Root Endpoint (/)"
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                assert "message" in data
                assert "version" in data
                assert "status" in data
                logger.info(f"✅ {test_name}")
                self.results[test_name] = {"status": "PASS", "response": data}
                self.passed += 1
                return True
            else:
                logger.error(f"❌ {test_name}: Status {response.status_code}")
                self.results[test_name] = {"status": "FAIL", "code": response.status_code}
                self.failed += 1
                return False
        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.results[test_name] = {"status": "ERROR", "error": str(e)}
            self.failed += 1
            return False

    def test_health_endpoint(self) -> bool:
        """Test health check endpoint."""
        test_name = "Health Check (/health)"
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                assert "status" in data
                logger.info(f"✅ {test_name}")
                self.results[test_name] = {"status": "PASS", "response": data}
                self.passed += 1
                return True
            else:
                logger.error(f"❌ {test_name}: Status {response.status_code}")
                self.results[test_name] = {"status": "FAIL", "code": response.status_code}
                self.failed += 1
                return False
        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.results[test_name] = {"status": "ERROR", "error": str(e)}
            self.failed += 1
            return False

    def test_system_status(self) -> bool:
        """Test system status endpoint."""
        test_name = "System Status (/api/system/status/)"
        try:
            response = requests.get(
                f"{self.base_url}/api/system/status/", timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                required_fields = [
                    "chromadb_connected",
                    "model_loaded",
                    "services_running",
                    "contestant_count",
                ]
                for field in required_fields:
                    assert field in data, f"Missing field: {field}"
                logger.info(f"✅ {test_name}")
                self.results[test_name] = {"status": "PASS", "response": data}
                self.passed += 1
                return True
            else:
                logger.error(f"❌ {test_name}: Status {response.status_code}")
                self.results[test_name] = {"status": "FAIL", "code": response.status_code}
                self.failed += 1
                return False
        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.results[test_name] = {"status": "ERROR", "error": str(e)}
            self.failed += 1
            return False

    def test_videos_endpoint(self) -> bool:
        """Test videos endpoint."""
        test_name = "Videos List (/api/videos/)"
        try:
            response = requests.get(f"{self.base_url}/api/videos/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, list), "Expected list response"
                if len(data) > 0:
                    assert "id" in data[0], "Missing 'id' field in video"
                    assert "name" in data[0], "Missing 'name' field in video"
                logger.info(f"✅ {test_name} ({len(data)} videos)")
                self.results[test_name] = {
                    "status": "PASS",
                    "video_count": len(data),
                }
                self.passed += 1
                return True
            else:
                logger.error(f"❌ {test_name}: Status {response.status_code}")
                self.results[test_name] = {"status": "FAIL", "code": response.status_code}
                self.failed += 1
                return False
        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.results[test_name] = {"status": "ERROR", "error": str(e)}
            self.failed += 1
            return False

    def test_contestants_endpoint(self) -> bool:
        """Test contestants endpoint."""
        test_name = "Contestants List (/api/contestants/)"
        try:
            response = requests.get(f"{self.base_url}/api/contestants/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, list), "Expected list response"
                if len(data) > 0:
                    assert "id" in data[0], "Missing 'id' field in contestant"
                    assert "name" in data[0], "Missing 'name' field in contestant"
                logger.info(f"✅ {test_name} ({len(data)} contestants)")
                self.results[test_name] = {
                    "status": "PASS",
                    "contestant_count": len(data),
                }
                self.passed += 1
                return True
            else:
                logger.error(f"❌ {test_name}: Status {response.status_code}")
                self.results[test_name] = {"status": "FAIL", "code": response.status_code}
                self.failed += 1
                return False
        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.results[test_name] = {"status": "ERROR", "error": str(e)}
            self.failed += 1
            return False

    def test_database_initialization(self) -> bool:
        """Test database initialization."""
        test_name = "Database Initialization"
        try:
            result = subprocess.run(
                [
                    "python",
                    "scripts/init_database.py",
                    "--verify",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and "✅ Data consistency: VALID" in result.stdout:
                logger.info(f"✅ {test_name}")
                self.results[test_name] = {"status": "PASS"}
                self.passed += 1
                return True
            else:
                logger.error(f"❌ {test_name}")
                self.results[test_name] = {
                    "status": "FAIL",
                    "output": result.stdout[-500:] if result.stdout else "No output",
                }
                self.failed += 1
                return False
        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.results[test_name] = {"status": "ERROR", "error": str(e)}
            self.failed += 1
            return False

    def run_all_tests(self) -> bool:
        """Run all tests."""
        logger.info("=" * 60)
        logger.info("Backend Health Test Suite")
        logger.info("=" * 60)

        logger.info("\n1️⃣  Checking backend status...")
        if not self.is_backend_running():
            logger.warning(
                f"⚠️  Backend not running at {self.base_url}"
            )
            logger.info("   Trying to start backend locally...")
            self._start_backend_locally()
            time.sleep(2)

        logger.info("\n2️⃣  Testing API endpoints...")
        self.test_root_endpoint()
        self.test_health_endpoint()
        self.test_system_status()
        self.test_videos_endpoint()
        self.test_contestants_endpoint()

        logger.info("\n3️⃣  Testing database initialization...")
        self.test_database_initialization()

        return self._print_report()

    def run_specific_test(self, test_name: str) -> bool:
        """Run specific test."""
        test_methods = {
            "root": self.test_root_endpoint,
            "health": self.test_health_endpoint,
            "status": self.test_system_status,
            "videos": self.test_videos_endpoint,
            "contestants": self.test_contestants_endpoint,
            "database": self.test_database_initialization,
        }

        if test_name not in test_methods:
            logger.error(f"Unknown test: {test_name}")
            logger.info(f"Available tests: {', '.join(test_methods.keys())}")
            return False

        logger.info(f"Running test: {test_name}")
        return test_methods[test_name]()

    def _start_backend_locally(self) -> None:
        """Attempt to start backend locally (non-blocking)."""
        try:
            subprocess.Popen(
                ["uvicorn", "backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("   Backend startup initiated (background)")
        except Exception as e:
            logger.warning(f"   Could not start backend: {e}")

    def _print_report(self) -> bool:
        """Print test report."""
        logger.info("\n" + "=" * 60)
        logger.info("Test Results")
        logger.info("=" * 60)

        for test_name, result in self.results.items():
            status = result["status"]
            emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
            logger.info(f"{emoji} {test_name}: {status}")

        logger.info("\n" + "=" * 60)
        logger.info(f"Summary: {self.passed} passed, {self.failed} failed")
        logger.info("=" * 60 + "\n")

        return self.failed == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test backend health endpoints")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Backend URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--test",
        help="Run specific test (root, health, status, videos, contestants, database)",
    )

    args = parser.parse_args()

    tester = BackendHealthTester(base_url=args.url)

    if args.test:
        success = tester.run_specific_test(args.test)
    else:
        success = tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
