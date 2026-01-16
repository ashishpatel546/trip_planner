#!/usr/bin/env python3
"""
Trip Planner - Start Both Servers
Cross-platform Python script to start API and Streamlit
"""

import subprocess
import sys
import time
import os
from pathlib import Path

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_info(text):
    print(f"📝 {text}")

def main():
    print_header("🚀 Starting Trip Planner Services")
    
    # Get script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Check for virtual environment
    print("📦 Checking virtual environment...")
    venv_python = script_dir / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
    
    if not venv_python.exists():
        print_error("Virtual environment not found!")
        print_info("Please run: uv sync")
        sys.exit(1)
    
    print_success("Virtual environment found")
    
    # Start API server
    print("\n🔧 Starting API Server (port 8000)...")
    api_cmd = [str(venv_python), "-m", "uvicorn", "trip_planner.api:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
    
    try:
        api_process = subprocess.Popen(
            api_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(3)
        
        if api_process.poll() is not None:
            print_error("API Server failed to start!")
            sys.exit(1)
        
        print_success(f"API Server started (PID: {api_process.pid})")
        print_info("API running at: http://localhost:8000")
        print_info("API docs at: http://localhost:8000/docs")
    except Exception as e:
        print_error(f"Failed to start API: {e}")
        sys.exit(1)
    
    # Start Streamlit
    print("\n🎨 Starting Streamlit Frontend (port 8501)...")
    streamlit_cmd = [str(venv_python), "-m", "streamlit", "run", "src/trip_planner/streamlit_app.py", "--server.port", "8501"]
    
    try:
        time.sleep(2)
        streamlit_process = subprocess.Popen(
            streamlit_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(3)
        
        if streamlit_process.poll() is not None:
            print_error("Streamlit failed to start!")
            print("⚠️  Stopping API Server...")
            api_process.terminate()
            sys.exit(1)
        
        print_success(f"Streamlit started (PID: {streamlit_process.pid})")
        print_info("Frontend at: http://localhost:8501")
    except Exception as e:
        print_error(f"Failed to start Streamlit: {e}")
        print("⚠️  Stopping API Server...")
        api_process.terminate()
        sys.exit(1)
    
    # Success message
    print_header("✅ ALL SERVICES RUNNING!")
    print("📝 Service URLs:")
    print("   🎨 Streamlit UI:  http://localhost:8501")
    print("   🔧 API Server:    http://localhost:8000")
    print("   📖 API Docs:      http://localhost:8000/docs")
    
    print("\n💡 Tips:")
    print("   • Your browser should open automatically")
    print("   • Press Ctrl+C to stop all servers")
    
    print("\n⏳ Servers are running... Press Ctrl+C to stop")
    
    # Wait for Ctrl+C
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down services...")
        streamlit_process.terminate()
        api_process.terminate()
        time.sleep(1)
        streamlit_process.kill()
        api_process.kill()
        print_success("Services stopped")

if __name__ == "__main__":
    main()
