#!/usr/bin/env python3
"""
Test a single question to Pal
"""

import requests
import time
from datetime import datetime

# API Configuration
API_BASE = "http://localhost:8000"
EMAIL = "support@skinsense.app"
PASSWORD = "Olaabdel@88aa"

def login():
    """Login and get access token"""
    response = requests.post(
        f"{API_BASE}/api/v1/auth/login",
        json={
            "email": EMAIL,
            "password": PASSWORD
        },
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Login failed: {response.status_code}")
        return None

def test_pal_question(token, question):
    """Test a single question"""
    print(f"\n🤖 Testing Pal with: '{question}'")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending request...")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/pal/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"message": question},
            timeout=20  # 20 second timeout
        )
        
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Response received in {elapsed_time:.2f} seconds")
            print(f"\n💬 Pal says:")
            print("=" * 60)
            print(data.get("response", "No response"))
            print("=" * 60)
            
            if data.get("suggestions"):
                print(f"\n💡 Follow-up suggestions:")
                for suggestion in data.get("suggestions", []):
                    print(f"  • {suggestion}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"⏱️ Request timed out after {elapsed_time:.2f} seconds")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

# Login
print("🔐 Logging in...")
token = login()

if token:
    print("✅ Login successful!")
    
    # Test different questions
    print("\n" + "=" * 60)
    print("TESTING DIFFERENT QUESTIONS")
    print("=" * 60)
    
    questions = [
        "What's a good morning routine for oily skin?",
        "How can I improve my dark circles?",
        "What ingredients help with radiance?",
        "Should I use retinol?",
        "How often should I exfoliate?",
        "What's the best way to layer serums?",
        "Can you explain my recent analysis?"
    ]
    
    print(f"\nChoose a question (1-{len(questions)}) or type your own:")
    for i, q in enumerate(questions, 1):
        print(f"{i}. {q}")
    print(f"{len(questions)+1}. Type your own question")
    
    choice = input("\nYour choice: ").strip()
    
    if choice.isdigit() and 1 <= int(choice) <= len(questions):
        question = questions[int(choice)-1]
    elif choice == str(len(questions)+1):
        question = input("Type your question: ").strip()
    else:
        question = choice  # Assume they typed a question directly
    
    test_pal_question(token, question)
else:
    print("❌ Failed to login")