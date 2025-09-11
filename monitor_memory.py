#!/usr/bin/env python3
"""
Memory usage monitoring script for MV Face Recognition system.
Shows real-time memory consumption of backend processes.
"""

import psutil
import time
import sys
from datetime import datetime


def get_process_memory(process_name):
    """Get memory usage for processes matching the given name."""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "memory_info", "cmdline"]):
        try:
            # Check for backend processes
            if process_name.lower() in proc.info["name"].lower() or any(
                process_name.lower() in arg.lower()
                for arg in proc.info["cmdline"]
                if arg
            ):
                processes.append(
                    {
                        "pid": proc.info["pid"],
                        "name": proc.info["name"],
                        "memory_mb": proc.info["memory_info"].rss / 1024 / 1024,
                        "cmdline": " ".join(proc.info["cmdline"][:3]),  # First 3 args
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


def format_memory(mb):
    """Format memory in MB or GB."""
    if mb > 1024:
        return f"{mb/1024:.1f} GB"
    return f"{mb:.1f} MB"


def monitor_system():
    """Monitor system memory usage."""
    print("🔍 MV Face Recognition - Memory Usage Monitor")
    print("=" * 60)
    print("Press Ctrl+C to stop monitoring\n")

    try:
        while True:
            # Clear screen (works on most terminals)
            print("\033[2J\033[H", end="")

            print(f"📊 Memory Usage Report - {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 60)

            # System memory
            system_mem = psutil.virtual_memory()
            print("🖥️  System Memory:")
            print(f"   Total: {format_memory(system_mem.total / 1024 / 1024)}")
            print(
                f"   Used:  {format_memory(system_mem.used / 1024 / 1024)} ({system_mem.percent:.1f}%)"
            )
            print(f"   Free:  {format_memory(system_mem.available / 1024 / 1024)}")
            print()

            # Backend processes (Python/FastAPI)
            backend_processes = get_process_memory("python")
            backend_processes.extend(get_process_memory("uvicorn"))

            total_backend_memory = 0
            if backend_processes:
                print("🔧 Backend Processes (Python/FastAPI):")
                for proc in backend_processes:
                    if "main:app" in proc["cmdline"] or "uvicorn" in proc["cmdline"]:
                        print(
                            f"   PID {proc['pid']}: {format_memory(proc['memory_mb'])} - {proc['cmdline']}"
                        )
                        total_backend_memory += proc["memory_mb"]
                print(f"   Total Backend: {format_memory(total_backend_memory)}")
            else:
                print("🔧 Backend Processes: Not running")
            print()

            # Frontend processes (Node.js)
            frontend_processes = get_process_memory("node")
            total_frontend_memory = 0
            if frontend_processes:
                print("🎨 Frontend Processes (Node.js/Vite):")
                for proc in frontend_processes:
                    if "vite" in proc["cmdline"] or "npm" in proc["cmdline"]:
                        print(
                            f"   PID {proc['pid']}: {format_memory(proc['memory_mb'])} - {proc['cmdline']}"
                        )
                        total_frontend_memory += proc["memory_mb"]
                print(f"   Total Frontend: {format_memory(total_frontend_memory)}")
            else:
                print("🎨 Frontend Processes: Not running")
            print()

            # GPU memory (if available)
            try:
                import GPUtil

                gpus = GPUtil.getGPUs()
                if gpus:
                    print("🎮 GPU Memory:")
                    for gpu in gpus:
                        used_mb = gpu.memoryUsed
                        total_mb = gpu.memoryTotal
                        print(
                            f"   {gpu.name}: {used_mb} MB / {total_mb} MB ({gpu.memoryUtil*100:.1f}%)"
                        )
                else:
                    print("🎮 GPU Memory: No GPUs detected")
            except ImportError:
                print("🎮 GPU Memory: GPUtil not installed (pip install gputil)")
            print()

            # Total system usage
            total_app_memory = total_backend_memory + total_frontend_memory
            print(f"📈 Total Application Memory: {format_memory(total_app_memory)}")

            # Performance targets from DESIGN.md
            print("\n🎯 Performance Targets:")
            print(
                f"   Server Memory Target: <2GB (Current: {format_memory(total_backend_memory)})"
            )
            print("   Browser Memory Target: <500MB (Check browser dev tools)")

            if total_backend_memory > 2000:
                print("   ⚠️  Backend memory usage exceeds target!")
            elif total_backend_memory > 0:
                print("   ✅ Backend memory usage within target")

            print("\n" + "=" * 60)
            print("Updating in 5 seconds... (Ctrl+C to stop)")

            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped")
        sys.exit(0)


if __name__ == "__main__":
    monitor_system()
