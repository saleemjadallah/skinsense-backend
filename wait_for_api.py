#!/usr/bin/env python3
"""
Wait for API to come online and then test Pal
"""

import requests
import time
from datetime import datetime

API_BASE = "http://54.211.215.150:8000"

def check_health():
    """Check if API is healthy"""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=3)
        return response.status_code == 200
    except:
        return False

print("🔄 Waiting for API to come online...")
print(f"   Checking {API_BASE}/health")

attempt = 1
while attempt <= 30:  # Try for up to 5 minutes
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Attempt {attempt}/30...", end=" ")
    
    if check_health():
        print("✅ API is online!")
        print("\n🚀 Running Pal performance test...")
        time.sleep(2)
        import subprocess
        subprocess.run(["python3", "test_pal_performance.py"])
        break
    else:
        print("⏳ API not ready yet")
        time.sleep(10)
        attempt += 1
else:
    print("\n❌ API did not come online after 5 minutes")
    print("   Please check the deployment logs on GitHub")