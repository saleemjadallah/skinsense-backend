#!/usr/bin/env python3
"""
Test Pal's response time with GPT-5-mini
"""

import requests
import time
import json
from datetime import datetime

# API Configuration
API_BASE = "http://localhost:8000"  # Testing locally first
EMAIL = "support@skinsense.app"
PASSWORD = "Olaabdel@88aa"

def login():
    """Login and get access token"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Logging in as {EMAIL}...")
    
    response = requests.post(
        f"{API_BASE}/api/v1/auth/login",
        json={
            "email": EMAIL,
            "password": PASSWORD
        },
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Login successful")
        return token
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Login failed: {response.status_code}")
        print(response.text)
        return None

def test_pal_chat(token, message):
    """Test Pal chat endpoint"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Testing Pal with message: '{message}'")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending request...")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/pal/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"message": message},
            timeout=15  # 15 second client-side timeout
        )
        
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Response received in {elapsed_time:.2f} seconds")
            print(f"\n📱 Pal's Response:")
            print("-" * 50)
            print(data.get("response", "No response"))
            print("-" * 50)
            
            if data.get("suggestions"):
                print(f"\n💡 Follow-up suggestions:")
                for suggestion in data.get("suggestions", []):
                    print(f"  • {suggestion}")
            
            return True, elapsed_time
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {response.status_code}")
            print(response.text)
            return False, elapsed_time
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️ Request timed out after {elapsed_time:.2f} seconds")
        return False, elapsed_time
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {str(e)}")
        return False, elapsed_time

def main():
    print("=" * 60)
    print("🤖 PAL PERFORMANCE TEST - GPT-5-mini")
    print("=" * 60)
    
    # Login
    token = login()
    if not token:
        print("\n❌ Failed to login. Exiting.")
        return
    
    # Test questions
    test_questions = [
        "How does vitamin C improve skin?",  # The question that was hanging
        "What's my skin score?",
        "Tell me about hydration",
        "What products should I use?"
    ]
    
    print(f"\n📊 Testing {len(test_questions)} questions...")
    print("=" * 60)
    
    results = []
    for i, question in enumerate(test_questions, 1):
        print(f"\n📝 Test {i}/{len(test_questions)}")
        success, response_time = test_pal_chat(token, question)
        results.append({
            "question": question,
            "success": success,
            "time": response_time
        })
        
        # Small delay between requests
        if i < len(test_questions):
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Waiting 2 seconds before next test...")
            time.sleep(2)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    successful_tests = [r for r in results if r["success"]]
    
    if successful_tests:
        avg_time = sum(r["time"] for r in successful_tests) / len(successful_tests)
        print(f"✅ Success Rate: {len(successful_tests)}/{len(results)} ({len(successful_tests)*100/len(results):.0f}%)")
        print(f"⏱️ Average Response Time: {avg_time:.2f} seconds")
        print(f"🚀 Fastest Response: {min(r['time'] for r in successful_tests):.2f} seconds")
        print(f"🐌 Slowest Response: {max(r['time'] for r in successful_tests):.2f} seconds")
    else:
        print("❌ All tests failed")
    
    print("\n📝 Individual Results:")
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} '{r['question']}' - {r['time']:.2f}s")
    
    print("\n" + "=" * 60)
    print("✨ Test Complete!")

if __name__ == "__main__":
    main()