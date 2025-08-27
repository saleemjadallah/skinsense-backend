#!/usr/bin/env python3
"""
Test various questions to Pal
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
    return None

def test_question(token, question):
    """Test a single question"""
    print(f"\n{'='*60}")
    print(f"📝 Question: '{question}'")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending...")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/pal/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"message": question},
            timeout=15
        )
        
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            response_text = data.get("response", "No response")
            
            # Truncate long responses for readability
            if len(response_text) > 300:
                response_preview = response_text[:300] + "..."
            else:
                response_preview = response_text
            
            print(f"✅ Success in {elapsed_time:.2f}s")
            print(f"Response preview: {response_preview}")
            return True, elapsed_time
        else:
            print(f"❌ Error {response.status_code} after {elapsed_time:.2f}s")
            return False, elapsed_time
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"⏱️ Timeout after {elapsed_time:.2f}s")
        return False, elapsed_time
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ Error: {str(e)[:50]} after {elapsed_time:.2f}s")
        return False, elapsed_time

print("🔐 Logging in...")
token = login()

if token:
    print("✅ Login successful!")
    
    # Test questions that should work quickly
    quick_questions = [
        "What's my skin score?",
        "How can I improve my radiance?",
        "What helps with dark circles?",
        "Should I use retinol?",
        "How often should I exfoliate?",
        "Tell me about niacinamide",
        "What's a good morning routine?",
        "How do I layer products?",
        "What ingredients help with acne?",
        "Can vitamin C and retinol be used together?"
    ]
    
    print(f"\n🧪 Testing {len(quick_questions)} questions...")
    
    results = []
    for question in quick_questions:
        success, time_taken = test_question(token, question)
        results.append((question, success, time_taken))
        
        # Small delay between requests
        if question != quick_questions[-1]:
            time.sleep(1)
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    
    successful = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]
    
    print(f"✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed/Timeout: {len(failed)}/{len(results)}")
    
    if successful:
        avg_time = sum(r[2] for r in successful) / len(successful)
        print(f"⏱️ Average response time: {avg_time:.2f}s")
        print(f"🚀 Fastest: {min(r[2] for r in successful):.2f}s")
        print(f"🐌 Slowest: {max(r[2] for r in successful):.2f}s")
    
    if failed:
        print(f"\n❌ Failed questions:")
        for q, _, t in failed:
            print(f"  • '{q}' ({t:.2f}s)")
else:
    print("❌ Login failed")