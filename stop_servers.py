#!/usr/bin/env python3
"""
Trip Planner - Stop All Servers
Cross-platform Python script to stop API and Streamlit servers
"""

import subprocess
import sys
import signal
import os

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_success(text):
    print(f"✅ {text}")

def print_warning(text):
    print(f"⚠️  {text}")

def find_and_kill_processes():
    """Find and kill Trip Planner processes"""
    killed_count = 0
    
    try:
        if sys.platform == "win32":
            # Windows: Use tasklist and taskkill
            # Find Python processes with uvicorn or streamlit
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Get PIDs of python processes
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line:
                        parts = line.replace('"', '').split(',')
                        if len(parts) >= 2:
                            pid = parts[1]
                            # Check if it's our process
                            try:
                                wmic_result = subprocess.run(
                                    ["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine", "/FORMAT:LIST"],
                                    capture_output=True,
                                    text=True,
                                    timeout=2
                                )
                                cmdline = wmic_result.stdout.lower()
                                if "uvicorn" in cmdline and "trip_planner" in cmdline or "streamlit" in cmdline:
                                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                                    killed_count += 1
                            except:
                                pass
        else:
            # macOS/Linux: Use ps and grep
            # Find uvicorn processes
            result = subprocess.run(
                ["pgrep", "-f", "uvicorn.*trip_planner"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        killed_count += 1
                    except:
                        pass
            
            # Find streamlit processes
            result = subprocess.run(
                ["pgrep", "-f", "streamlit.*trip_planner"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        killed_count += 1
                    except:
                        pass
    
    except Exception as e:
        print(f"Error finding processes: {e}")
    
    return killed_count

def main():
    print_header("🛑 Stopping Trip Planner Services")
    
    killed = find_and_kill_processes()
    
    if killed > 0:
        print_success(f"Stopped {killed} process(es)")
    else:
        print_warning("No Trip Planner processes found")
    
    print_header("✅ All services stopped")

if __name__ == "__main__":
    main()
