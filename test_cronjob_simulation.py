#!/usr/bin/env python3
"""
Test script to simulate the exact cronjob environment for daily insights
This script matches exactly what happens in the Docker container cron job
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path (same as in cronjob script)
sys.path.append(str(Path(__file__).parent))

async def test_daily_insights_generation():
    """Test the actual daily insights generation process"""
    print("🔍 Testing Daily Insights Generation (Cronjob Simulation)")
    print("=" * 60)
    
    try:
        # Import the same way the cronjob does
        from app.database import db
        from app.services.insights_service import get_insights_service
        from app.core.config import settings
        import logging
        
        # Configure logging the same way
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        
        logger = logging.getLogger(__name__)
        
        print(f"✅ Imports successful")
        print(f"📊 OpenAI API Key: {settings.OPENAI_API_KEY[:10] if settings.OPENAI_API_KEY else 'EMPTY'}...")
        
        # Test database connection
        try:
            user_count = db.users.count_documents({"is_active": True})
            print(f"✅ Database connection successful - {user_count} active users found")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
        
        # Test insights service initialization
        try:
            insights_service = get_insights_service()
            print(f"✅ Insights service initialized")
            
            # Check OpenAI client
            if hasattr(insights_service, 'openai_client') and insights_service.openai_client:
                api_key = insights_service.openai_client.api_key
                if api_key and api_key != "your-openai-api-key-here":
                    print(f"✅ OpenAI client properly configured")
                    
                    # Test a simple OpenAI call
                    try:
                        import openai
                        test_response = insights_service.openai_client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": "Test"}],
                            max_tokens=5
                        )
                        print(f"✅ OpenAI API call successful")
                        return True
                    except Exception as e:
                        print(f"❌ OpenAI API call failed: {e}")
                        return False
                else:
                    print(f"❌ OpenAI API key is placeholder or empty")
                    return False
            else:
                print(f"❌ OpenAI client not properly initialized")
                return False
                
        except Exception as e:
            print(f"❌ Insights service initialization failed: {e}")
            import traceback
            print(traceback.format_exc())
            return False
            
    except Exception as e:
        print(f"❌ Failed to import required modules: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def check_environment_setup():
    """Check the environment setup for the cronjob"""
    print("\n🔧 Environment Setup Check")
    print("=" * 40)
    
    # Check Python path
    print(f"📍 Python executable: {sys.executable}")
    print(f"📍 Current working directory: {os.getcwd()}")
    print(f"📍 Python path: {sys.path[:3]}...")
    
    # Check critical environment variables
    env_vars = [
        "OPENAI_API_KEY",
        "MONGODB_URL", 
        "DEBUG",
        "ENVIRONMENT"
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "API_KEY" in var or "URL" in var:
                display_value = f"{value[:10]}...{value[-4:]}" if len(value) > 14 else value
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: Not set")
    
    # Check .env file
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        print(f"✅ .env file exists")
        
        try:
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            openai_lines = [line for line in lines if line.strip().startswith('OPENAI_API_KEY')]
            if openai_lines:
                line = openai_lines[0].strip()
                if '=' in line:
                    key_value = line.split('=', 1)[1].strip()
                    if key_value and key_value != 'your-openai-api-key-here':
                        print(f"✅ .env has valid-looking OpenAI key")
                    else:
                        print(f"❌ .env has placeholder OpenAI key: {key_value}")
                else:
                    print(f"❌ .env has malformed OpenAI key line")
            else:
                print(f"❌ .env missing OPENAI_API_KEY")
                
        except Exception as e:
            print(f"❌ Error reading .env file: {e}")
    else:
        print(f"❌ .env file not found")

async def main():
    """Main test function"""
    check_environment_setup()
    
    success = await test_daily_insights_generation()
    
    print("\n" + "=" * 60)
    print("📊 CRONJOB SIMULATION SUMMARY")
    print("=" * 60)
    
    if success:
        print("🎉 SUCCESS: Daily insights cronjob should work correctly!")
        print("✅ OpenAI API key is properly configured")
        print("✅ All services can be initialized")
        print("✅ API calls are working")
    else:
        print("⚠️  FAILURE: Daily insights cronjob will NOT work correctly!")
        print("\n🛠️  REQUIRED FIXES:")
        print("1. Set a valid OpenAI API key in the .env file")
        print("2. Ensure the API key has sufficient credits")
        print("3. Verify the key has access to the required models (gpt-4-turbo-preview)")
        print("4. Test the configuration in the Docker container environment")

if __name__ == "__main__":
    asyncio.run(main())
