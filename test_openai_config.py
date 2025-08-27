#!/usr/bin/env python3
"""
Test script to verify OpenAI API key configuration for daily insights cronjob
This script simulates the environment that the cronjob runs in to diagnose issues
"""

import sys
import os
from pathlib import Path

# Add app directory to path (same as in cronjob script)
sys.path.append(str(Path(__file__).parent / "app"))

def test_environment_variables():
    """Test if environment variables are properly loaded"""
    print("=== Environment Variables Test ===")
    
    # Check if OPENAI_API_KEY is in environment
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        print(f"✅ OPENAI_API_KEY found in environment: {openai_key[:10]}...{openai_key[-4:]}")
    else:
        print("❌ OPENAI_API_KEY not found in environment variables")
    
    # Check other related variables
    debug = os.getenv("DEBUG", "Not set")
    mongodb_url = os.getenv("MONGODB_URL", "Not set")
    
    print(f"📊 DEBUG: {debug}")
    print(f"📊 MONGODB_URL: {mongodb_url[:20]}...{mongodb_url[-10:] if len(mongodb_url) > 30 else mongodb_url}")
    
    return openai_key is not None

def test_config_loading():
    """Test if the configuration files are loading correctly"""
    print("\n=== Configuration Loading Test ===")
    
    try:
        # Test both config files
        try:
            from app.core.config import settings as core_settings
            print(f"✅ Core config loaded - OPENAI_API_KEY: {core_settings.OPENAI_API_KEY[:10] if core_settings.OPENAI_API_KEY else 'EMPTY'}...")
            core_key = core_settings.OPENAI_API_KEY
        except Exception as e:
            print(f"❌ Failed to load core config: {e}")
            core_key = None
        
        try:
            from app.config import settings as app_settings
            print(f"✅ App config loaded - openai_api_key: {app_settings.openai_api_key[:10] if app_settings.openai_api_key else 'EMPTY'}...")
            app_key = app_settings.openai_api_key
        except Exception as e:
            print(f"❌ Failed to load app config: {e}")
            app_key = None
            
        return core_key or app_key
        
    except Exception as e:
        print(f"❌ Error loading configurations: {e}")
        return None

def test_insights_service():
    """Test if the insights service can be initialized with OpenAI"""
    print("\n=== Insights Service Test ===")
    
    try:
        from app.services.insights_service import get_insights_service
        
        insights_service = get_insights_service()
        
        # Check if OpenAI client is initialized
        if hasattr(insights_service, 'openai_client'):
            print("✅ InsightsService OpenAI client initialized")
            
            # Check if the API key is set in the client
            if hasattr(insights_service.openai_client, 'api_key'):
                key = insights_service.openai_client.api_key
                if key:
                    print(f"✅ OpenAI client has API key: {key[:10]}...{key[-4:]}")
                    return True
                else:
                    print("❌ OpenAI client has no API key")
                    return False
            else:
                print("❌ OpenAI client has no api_key attribute")
                return False
        else:
            print("❌ InsightsService has no openai_client attribute")
            return False
            
    except Exception as e:
        print(f"❌ Error testing insights service: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def test_openai_service():
    """Test if the OpenAI service can be initialized"""
    print("\n=== OpenAI Service Test ===")
    
    try:
        from app.services.openai_service import openai_service
        
        # Check if OpenAI client is initialized
        if hasattr(openai_service, 'client'):
            print("✅ OpenAIService client initialized")
            
            # Check if the API key is set in the client
            if hasattr(openai_service.client, 'api_key'):
                key = openai_service.client.api_key
                if key:
                    print(f"✅ OpenAI service has API key: {key[:10]}...{key[-4:]}")
                    return True
                else:
                    print("❌ OpenAI service has no API key")
                    return False
            else:
                print("❌ OpenAI client has no api_key attribute")
                return False
        else:
            print("❌ OpenAI service has no client attribute")
            return False
            
    except Exception as e:
        print(f"❌ Error testing OpenAI service: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def test_simple_openai_call():
    """Test a simple OpenAI API call"""
    print("\n=== Simple OpenAI API Call Test ===")
    
    try:
        import openai
        from app.core.config import settings
        
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Say 'Hello from SkinSense!'"}
            ],
            max_tokens=10
        )
        
        result = response.choices[0].message.content
        print(f"✅ OpenAI API call successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API call failed: {e}")
        return False

def check_env_file():
    """Check if .env file exists and contains OpenAI key"""
    print("\n=== .env File Check ===")
    
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        print(f"✅ .env file exists at: {env_file}")
        
        try:
            with open(env_file, 'r') as f:
                content = f.read()
                
            if "OPENAI_API_KEY" in content:
                lines = content.split('\n')
                openai_lines = [line for line in lines if line.startswith('OPENAI_API_KEY')]
                if openai_lines:
                    line = openai_lines[0]
                    if '=' in line and len(line.split('=')[1].strip()) > 0:
                        print(f"✅ OPENAI_API_KEY found in .env file")
                        return True
                    else:
                        print("❌ OPENAI_API_KEY in .env file but value is empty")
                        return False
                else:
                    print("❌ OPENAI_API_KEY not found in .env file")
                    return False
            else:
                print("❌ OPENAI_API_KEY not found in .env file")
                return False
                
        except Exception as e:
            print(f"❌ Error reading .env file: {e}")
            return False
    else:
        print(f"❌ .env file not found at: {env_file}")
        return False

def main():
    """Run all diagnostic tests"""
    print("🔍 SkinSense OpenAI Configuration Diagnostic")
    print("=" * 50)
    
    results = []
    
    # Test environment variables
    results.append(("Environment Variables", test_environment_variables()))
    
    # Check .env file
    results.append((".env File", check_env_file()))
    
    # Test configuration loading
    results.append(("Configuration Loading", test_config_loading()))
    
    # Test insights service
    results.append(("Insights Service", test_insights_service()))
    
    # Test OpenAI service
    results.append(("OpenAI Service", test_openai_service()))
    
    # Test simple API call
    results.append(("OpenAI API Call", test_simple_openai_call()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! OpenAI configuration is working correctly.")
    else:
        print("⚠️  Some tests failed. The daily insights cronjob may not work properly.")
        print("\nRecommendations:")
        if not results[0][1]:  # Environment variables
            print("- Check that OPENAI_API_KEY is set in the Docker container environment")
        if not results[1][1]:  # .env file
            print("- Ensure .env file exists and contains OPENAI_API_KEY=your-actual-key")
        if not results[2][1]:  # Configuration loading
            print("- Verify that the configuration files can access environment variables")
        if not results[3][1] or not results[4][1]:  # Services
            print("- Check that the services are correctly importing the configuration")
        if not results[5][1]:  # API call
            print("- Verify that the OpenAI API key is valid and has sufficient credits")

if __name__ == "__main__":
    main()
