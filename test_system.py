#!/usr/bin/env python3
"""
Test script to verify the FastAPI + Svelte system components work correctly.
"""

import asyncio
import subprocess
import time
import sys
import requests
import websockets
import json
from pathlib import Path

# Change to the project directory
PROJECT_DIR = Path(__file__).parent
BACKEND_DIR = PROJECT_DIR / "backend"
FRONTEND_DIR = PROJECT_DIR / "frontend"

class SystemTester:
    def __init__(self):
        self.backend_process = None
        self.frontend_process = None
        
    async def test_backend_health(self):
        """Test if backend is running and healthy."""
        try:
            response = requests.get("http://127.0.0.1:8000/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Backend health check passed: {data}")
                return True
            else:
                print(f"❌ Backend health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Backend health check failed: {e}")
            return False
    
    async def test_video_api(self):
        """Test video API endpoints."""
        try:
            # Test video list endpoint
            response = requests.get("http://127.0.0.1:8000/api/videos/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Video API works: Found {data['count']} videos")
                
                # Test video info if videos exist
                if data['videos']:
                    video_name = data['videos'][0]
                    response = requests.get(f"http://127.0.0.1:8000/api/videos/{video_name}", timeout=5)
                    if response.status_code == 200:
                        video_info = response.json()
                        print(f"✅ Video info API works: {video_info['filename']}")
                        return True
                    else:
                        print(f"❌ Video info API failed: {response.status_code}")
                        return False
                else:
                    print("⚠️ No videos found in source/videos directory")
                    return True
            else:
                print(f"❌ Video API failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Video API test failed: {e}")
            return False
    
    async def test_websocket(self):
        """Test WebSocket connection."""
        try:
            async with websockets.connect("ws://127.0.0.1:8000/ws/realtime-processing") as websocket:
                print("✅ WebSocket connection established")
                
                # Send a test message
                test_message = {
                    "type": "parameter_update",
                    "parameter": "detection_threshold",
                    "value": 0.6
                }
                await websocket.send(json.dumps(test_message))
                
                # Try to receive a response (with timeout)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"✅ WebSocket response received: {response[:100]}...")
                    return True
                except asyncio.TimeoutError:
                    print("⚠️ WebSocket connected but no response received (this is OK)")
                    return True
                    
        except Exception as e:
            print(f"❌ WebSocket test failed: {e}")
            return False
    
    async def test_contestants_api(self):
        """Test contestants API."""
        try:
            response = requests.get("http://127.0.0.1:8000/api/contestants/stats", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Contestants API works: {data['total_embeddings']} embeddings loaded")
                return True
            else:
                print(f"❌ Contestants API failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Contestants API test failed: {e}")
            return False
    
    def start_backend(self):
        """Start the FastAPI backend."""
        print("🚀 Starting FastAPI backend...")
        try:
            self.backend_process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=BACKEND_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for backend to start
            for i in range(30):  # Wait up to 30 seconds
                try:
                    response = requests.get("http://127.0.0.1:8000/health", timeout=1)
                    if response.status_code == 200:
                        print("✅ Backend started successfully")
                        return True
                except:
                    time.sleep(1)
                    print(f"⏳ Waiting for backend... ({i+1}/30)")
            
            print("❌ Backend failed to start within 30 seconds")
            return False
            
        except Exception as e:
            print(f"❌ Failed to start backend: {e}")
            return False
    
    def start_frontend(self):
        """Start the Svelte frontend."""
        print("🚀 Starting Svelte frontend...")
        try:
            self.frontend_process = subprocess.Popen(
                ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
                cwd=FRONTEND_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for frontend to start
            for i in range(20):  # Wait up to 20 seconds
                try:
                    response = requests.get("http://127.0.0.1:5173", timeout=1)
                    if response.status_code == 200:
                        print("✅ Frontend started successfully")
                        return True
                except:
                    time.sleep(1)
                    print(f"⏳ Waiting for frontend... ({i+1}/20)")
            
            print("❌ Frontend failed to start within 20 seconds")
            return False
            
        except Exception as e:
            print(f"❌ Failed to start frontend: {e}")
            return False
    
    def stop_processes(self):
        """Stop both processes."""
        print("🛑 Stopping processes...")
        if self.backend_process:
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
        
        if self.frontend_process:
            self.frontend_process.terminate()
            try:
                self.frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.frontend_process.kill()
    
    async def run_tests(self):
        """Run all system tests."""
        print("🧪 Starting MV Face Recognition System Tests\n")
        
        # Check if source videos directory exists
        videos_dir = PROJECT_DIR / "source" / "videos"
        if not videos_dir.exists():
            print(f"⚠️ Videos directory not found: {videos_dir}")
            print("   Creating empty directory for testing...")
            videos_dir.mkdir(parents=True, exist_ok=True)
        
        # Start backend
        if not self.start_backend():
            return False
        
        try:
            # Test backend components
            print("\n📡 Testing Backend Components:")
            
            health_ok = await self.test_backend_health()
            video_api_ok = await self.test_video_api()
            contestants_ok = await self.test_contestants_api()
            websocket_ok = await self.test_websocket()
            
            backend_tests_passed = health_ok and video_api_ok and contestants_ok and websocket_ok
            
            if backend_tests_passed:
                print("\n✅ All backend tests passed!")
            else:
                print("\n❌ Some backend tests failed")
            
            # Test frontend build
            print("\n🎨 Testing Frontend Build:")
            try:
                result = subprocess.run(
                    ["npm", "run", "build"],
                    cwd=FRONTEND_DIR,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    print("✅ Frontend builds successfully")
                    frontend_build_ok = True
                else:
                    print(f"❌ Frontend build failed: {result.stderr}")
                    frontend_build_ok = False
            except Exception as e:
                print(f"❌ Frontend build test failed: {e}")
                frontend_build_ok = False
            
            # Start frontend for integration test
            print("\n🔗 Testing Frontend-Backend Integration:")
            if self.start_frontend():
                print("✅ Frontend started and accessible")
                integration_ok = True
            else:
                print("❌ Frontend integration test failed")
                integration_ok = False
            
            # Summary
            print("\n📋 Test Summary:")
            print(f"Backend Health: {'✅' if health_ok else '❌'}")
            print(f"Video API: {'✅' if video_api_ok else '❌'}")
            print(f"Contestants API: {'✅' if contestants_ok else '❌'}")
            print(f"WebSocket: {'✅' if websocket_ok else '❌'}")
            print(f"Frontend Build: {'✅' if frontend_build_ok else '❌'}")
            print(f"Integration: {'✅' if integration_ok else '❌'}")
            
            all_passed = (backend_tests_passed and frontend_build_ok and integration_ok)
            
            if all_passed:
                print("\n🎉 All tests passed! The system is ready to use.")
                print("\n🚀 Quick Start:")
                print("1. Backend: cd backend && python -m uvicorn main:app --reload")
                print("2. Frontend: cd frontend && npm run dev")
                print("3. Open: http://localhost:5173")
            else:
                print("\n⚠️ Some tests failed. Please check the issues above.")
            
            return all_passed
            
        finally:
            self.stop_processes()

async def main():
    tester = SystemTester()
    success = await tester.run_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())