#!/usr/bin/env python3
"""
Test runner for MV Face Recognition System.
Provides convenient commands for running different types of tests.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"🔥 {description}")
    print(f"{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} - PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED (exit code: {e.returncode})")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run tests for MV Face Recognition System")
    parser.add_argument(
        "test_type", 
        choices=["all", "unit", "integration", "core", "services", "utils", "slow", "fast", "cpu", "gpu"],
        nargs="?",
        default="fast",
        help="Type of tests to run"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--coverage", "-c", action="store_true", help="Generate coverage report")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--parallel", "-p", action="store_true", help="Run tests in parallel")
    parser.add_argument("--failed", "-f", action="store_true", help="Run only failed tests from last run")
    parser.add_argument("--benchmark", "-b", action="store_true", help="Run benchmark tests")
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add verbose flag
    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    # Add coverage
    if args.coverage:
        cmd.extend(["--cov=src", "--cov-report=term-missing"])
        if args.html:
            cmd.append("--cov-report=html")
    
    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", "auto"])
    
    # Add failed tests only
    if args.failed:
        cmd.append("--lf")
    
    # Add benchmark support
    if args.benchmark:
        cmd.append("--benchmark-only")
    
    # Select test type
    if args.test_type == "all":
        cmd.append("tests/")
    elif args.test_type == "unit":
        cmd.extend(["-m", "unit", "tests/"])
    elif args.test_type == "integration":
        cmd.extend(["-m", "integration", "tests/"])
    elif args.test_type == "core":
        cmd.append("tests/test_core.py")
    elif args.test_type == "services":
        cmd.append("tests/test_services.py")
    elif args.test_type == "utils":
        cmd.append("tests/test_utils.py")
    elif args.test_type == "slow":
        cmd.extend(["-m", "slow", "tests/"])
    elif args.test_type == "fast":
        cmd.extend(["-m", "not slow", "tests/"])
    elif args.test_type == "cpu":
        cmd.extend(["-m", "cpu_only", "tests/"])
    elif args.test_type == "gpu":
        cmd.extend(["-m", "gpu", "tests/"])
    
    # Run the tests
    success = run_command(cmd, f"Running {args.test_type} tests")
    
    # Additional commands based on results
    if success and args.coverage and args.html:
        print(f"\n📊 Coverage report generated in htmlcov/index.html")
    
    if not success:
        print(f"\n💡 To run only failed tests next time, use: python run_tests.py --failed")
        print(f"💡 For more verbose output, use: python run_tests.py {args.test_type} --verbose")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()