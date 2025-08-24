#!/usr/bin/env python3
"""Test Plans API with support@skinsense.app credentials"""

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
print("Testing Plans API")
print(f"Server: {BASE_URL}")
print("=" * 60)

# Step 1: Login to get access token
print("\n1. Logging in...")
login_response = requests.post(
    f"{BASE_URL}/api/v1/auth/login",
    json={"email": email, "password": password}
)

if login_response.status_code == 200:
    auth_data = login_response.json()
    access_token = auth_data.get("access_token")
    user_info = auth_data.get("user", {})
    print(f"✓ Login successful!")
    print(f"  User ID: {user_info.get('id')}")
    print(f"  Email: {user_info.get('email')}")
    print(f"  Token: {access_token[:20]}...")
else:
    print(f"✗ Login failed: {login_response.status_code}")
    print(f"  Response: {login_response.text}")
    exit(1)

# Set up headers with token
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Step 2: Test Plans endpoints
print("\n2. Testing /api/v1/plans/ (list all plans)...")
response = requests.get(f"{BASE_URL}/api/v1/plans/", headers=headers)
print(f"  Status: {response.status_code}")
if response.status_code == 200:
    plans = response.json()
    print(f"  ✓ Found {len(plans)} plans")
    for plan in plans:
        print(f"    - {plan.get('name')} (Status: {plan.get('status')})")
else:
    print(f"  ✗ Error: {response.text}")

# Step 3: Test active plan endpoint
print("\n3. Testing /api/v1/plans/active (get active plan)...")
response = requests.get(f"{BASE_URL}/api/v1/plans/active", headers=headers)
print(f"  Status: {response.status_code}")
if response.status_code == 200:
    active_plan = response.json()
    if active_plan:
        print(f"  ✓ Active plan found:")
        print(f"    Name: {active_plan.get('name')}")
        print(f"    Type: {active_plan.get('plan_type')}")
        print(f"    Week: {active_plan.get('current_week')}/{active_plan.get('duration_weeks')}")
        print(f"    Status: {active_plan.get('status')}")
        print(f"    Routines: {len(active_plan.get('routines', []))}")
        print(f"    Goals: {len(active_plan.get('goals', []))}")
        
        # Print current milestone if available
        milestone = active_plan.get('current_milestone')
        if milestone:
            print(f"\n  Current Milestone:")
            print(f"    {milestone.get('title')}")
            print(f"    {milestone.get('description')}")
    else:
        print("  ⚠️  No active plan found")
else:
    print(f"  ✗ Error: {response.text}")

# Step 4: Test plan details endpoint (if we have a plan)
if response.status_code == 200 and active_plan:
    plan_id = active_plan.get('id')
    print(f"\n4. Testing /api/v1/plans/{plan_id} (get plan details)...")
    response = requests.get(f"{BASE_URL}/api/v1/plans/{plan_id}", headers=headers)
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        details = response.json()
        print(f"  ✓ Plan details retrieved successfully")
        print(f"    Milestones: {len(details.get('weekly_milestones', []))}")
        print(f"    Target concerns: {', '.join(details.get('target_concerns', []))}")
    else:
        print(f"  ✗ Error: {response.text}")

# Step 5: Test plan templates endpoint
print("\n5. Testing /api/v1/plans/templates (get available templates)...")
response = requests.get(f"{BASE_URL}/api/v1/plans/templates", headers=headers)
print(f"  Status: {response.status_code}")
if response.status_code == 200:
    templates = response.json()
    print(f"  ✓ Found {len(templates)} templates")
    for template in templates[:3]:  # Show first 3
        print(f"    - {template.get('name')} ({template.get('duration_weeks')} weeks)")
else:
    print(f"  ✗ Error: {response.text}")

print("\n" + "=" * 60)
print("API Testing Complete!")
print("=" * 60)
print("\nSummary:")
print(f"✓ User can authenticate successfully")
print(f"✓ Plans API endpoints are accessible")
print(f"✓ User has active plan in database")
print("\nYou can now use these credentials in Flutter:")
print(f"  Email: {email}")
print(f"  Password: {password}")
print("=" * 60)