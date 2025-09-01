#!/usr/bin/env python3
"""Test achievement API endpoint directly"""

import requests
import json
from datetime import datetime

# API configuration
API_BASE = "http://56.228.12.81:8080"
HEADERS = {
    "Host": "api.skinsense.ai",
    "Content-Type": "application/json"
}

def login_user(email, password):
    """Login and get access token"""
    print(f"\n🔐 Logging in as {email}...")
    
    response = requests.post(
        f"{API_BASE}/api/v1/auth/login",
        headers=HEADERS,
        json={
            "username": email,
            "password": password
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Login successful")
        return data.get("access_token")
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)
        return None

def get_achievements(token, sync=True):
    """Get user's achievements"""
    print(f"\n🏆 Fetching achievements (sync={sync})...")
    
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{API_BASE}/api/v1/achievements?sync={sync}",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Retrieved {data['total']} achievements ({data['unlocked']} unlocked)")
        
        # Find First Glow and Progress Pioneer
        for ach in data['achievements']:
            if ach['achievement_id'] in ['first_glow', 'progress_pioneer']:
                print(f"\n  📌 {ach['achievement_id']}:")
                print(f"     Title: {ach.get('title', 'N/A')}")
                print(f"     Progress: {ach.get('progress', 0) * 100:.0f}%")
                print(f"     Unlocked: {ach.get('is_unlocked', False)}")
                print(f"     Points: {ach.get('points', 0)}")
                if ach.get('progress_data'):
                    print(f"     Data: {ach['progress_data']}")
        
        return data
    else:
        print(f"❌ Failed to get achievements: {response.status_code}")
        print(response.text)
        return None

def force_sync(token):
    """Force sync achievements"""
    print(f"\n🔄 Force syncing achievements...")
    
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    
    response = requests.post(
        f"{API_BASE}/api/v1/achievements/sync",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Sync complete:")
        print(f"   Synced: {data.get('synced_achievements', 0)} achievements")
        print(f"   Analyses: {data.get('analysis_count', 0)}")
        print(f"   Goals: {data.get('goal_count', 0)}")
        print(f"   Routines: {data.get('routine_count', 0)}")
        return data
    else:
        print(f"❌ Sync failed: {response.status_code}")
        print(response.text)
        return None

def main():
    print("=" * 60)
    print("Achievement API Test")
    print("=" * 60)
    
    # Test with the Apple user
    # You may need to use the actual password or create a test token
    token = login_user("saleem86@icloud.com", "Test1234!")  # Use actual password
    
    if not token:
        print("\n⚠️  Cannot proceed without authentication")
        print("Please update the password or use a valid token")
        return
    
    # Test 1: Get achievements without sync
    print("\n--- Test 1: Get achievements WITHOUT sync ---")
    get_achievements(token, sync=False)
    
    # Test 2: Force sync
    print("\n--- Test 2: Force sync ---")
    force_sync(token)
    
    # Test 3: Get achievements with sync
    print("\n--- Test 3: Get achievements WITH sync ---")
    get_achievements(token, sync=True)
    
    print("\n" + "=" * 60)
    print("Test complete!")

if __name__ == "__main__":
    main()