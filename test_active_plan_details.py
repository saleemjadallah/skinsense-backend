#!/usr/bin/env python3
"""Test what the active plan API actually returns"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API configuration
BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')

# User credentials
email = os.getenv('TEST_SUPPORT_EMAIL', 'support@skinsense.app')
password = os.getenv('TEST_SUPPORT_PASSWORD', 'TestPassword123!')

print("=" * 60)
print("Testing Active Plan Details")
print("=" * 60)

# Login
print("\n1. Logging in...")
login_response = requests.post(
    f"{BASE_URL}/api/v1/auth/login",
    json={"email": email, "password": password}
)

if login_response.status_code != 200:
    print(f"✗ Login failed: {login_response.status_code}")
    exit(1)

auth_data = login_response.json()
access_token = auth_data.get("access_token")
print(f"✓ Logged in successfully")

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Get active plan
print("\n2. Fetching active plan...")
response = requests.get(f"{BASE_URL}/api/v1/plans/active", headers=headers)

if response.status_code == 200:
    plan = response.json()
    print(f"✓ Active plan retrieved")
    
    # Pretty print the entire response
    print("\nFull API Response:")
    print(json.dumps(plan, indent=2))
    
    # Specifically check routines and goals
    print("\n" + "=" * 60)
    print("Key Fields:")
    print(f"Name: {plan.get('name')}")
    print(f"Status: {plan.get('status')}")
    print(f"Current Week: {plan.get('current_week')}/{plan.get('duration_weeks')}")
    
    print(f"\nRoutines ({len(plan.get('routines', []))}):")
    for r in plan.get('routines', []):
        print(f"  - {r}")
    
    print(f"\nGoals ({len(plan.get('goals', []))}):")
    for g in plan.get('goals', []):
        print(f"  - {g}")
    
    print(f"\nCurrent Week Stats:")
    stats = plan.get('current_week_stats', {})
    print(f"  - Completion Rate: {stats.get('completion_rate')}%")
    print(f"  - Routines Completed: {stats.get('routines_completed')}")
    print(f"  - Days Remaining: {stats.get('days_remaining')}")
    
else:
    print(f"✗ Failed to get active plan: {response.status_code}")
    print(f"Error: {response.text}")

print("\n" + "=" * 60)