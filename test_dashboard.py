#!/usr/bin/env python3
"""
Test script for the new Face Recognition Dashboard.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_dashboard_import():
    """Test if the dashboard can be imported successfully."""
    try:
        from dashboard_gradio import (
            FaceRecognitionDashboard,
            create_dashboard_interface,
        )
        print("✅ Dashboard import successful")
        return True
    except ImportError as e:
        print(f"❌ Dashboard import failed: {e}")
        return False

def test_gradio_availability():
    """Test if Gradio is available."""
    try:
        import gradio as gr
        print(f"✅ Gradio available: {gr.__version__}")
        return True
    except ImportError as e:
        print(f"❌ Gradio not available: {e}")
        return False

def test_dependencies():
    """Test if required dependencies are available."""
    deps = {
        'cv2': 'opencv-python',
        'numpy': 'numpy',
        'pandas': 'pandas',
        'logging': 'built-in',
    }

    success = True
    for module, package in deps.items():
        try:
            __import__(module)
            print(f"✅ {module} ({package}) available")
        except ImportError:
            print(f"❌ {module} ({package}) not available")
            success = False

    return success

def test_dashboard_creation():
    """Test if dashboard can be created."""
    try:
        from dashboard_gradio import FaceRecognitionDashboard
        dashboard = FaceRecognitionDashboard()
        print("✅ Dashboard instance created successfully")

        # Test video availability
        videos, mapping = dashboard.get_available_videos()
        print(f"✅ Found {len(videos)} available videos")

        return True
    except Exception as e:
        print(f"❌ Dashboard creation failed: {e}")
        return False

def test_interface_creation():
    """Test if the interface can be created."""
    try:
        from dashboard_gradio import create_dashboard_interface
        create_dashboard_interface()
        print("✅ Dashboard interface created successfully")
        return True
    except Exception as e:
        print(f"❌ Interface creation failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Face Recognition Dashboard")
    print("=" * 50)

    tests = [
        ("Gradio Availability", test_gradio_availability),
        ("Dependencies", test_dependencies),
        ("Dashboard Import", test_dashboard_import),
        ("Dashboard Creation", test_dashboard_creation),
        ("Interface Creation", test_interface_creation),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)

    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")

    passed = sum(results)
    total = len(results)

    for i, (test_name, _) in enumerate(tests):
        status = "✅ PASS" if results[i] else "❌ FAIL"
        print(f"  {test_name}: {status}")

    print(f"\n🎯 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Dashboard is ready to use.")
        print("\n💡 To launch the dashboard, run:")
        print("   python dashboard_gradio.py")
    else:
        print("⚠️  Some tests failed. Please check the dependencies and configuration.")

        if not results[0]:  # Gradio failed
            print("\n💡 Install Gradio with: pip install gradio")
        if not results[1]:  # Dependencies failed
            print("\n💡 Install missing dependencies from requirements.txt")

if __name__ == "__main__":
    main()
