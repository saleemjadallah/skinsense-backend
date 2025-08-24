#!/usr/bin/env python3
"""
Initialize all MongoDB collections for Goals and Routines services
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import connect_to_mongo, get_database
from init_goal_templates import create_goal_templates, create_achievement_definitions
from init_routine_templates import create_routine_templates


def check_collections():
    """Check which collections exist and their document counts"""
    db = get_database()
    
    collections = [
        "goals",
        "routines", 
        "goal_progress",
        "routine_completions",
        "achievements",
        "goal_templates",
        "routine_templates"
    ]
    
    print("=== Collection Status ===")
    for collection_name in collections:
        try:
            count = db[collection_name].count_documents({})
            print(f"✓ {collection_name}: {count} documents")
        except Exception as e:
            print(f"✗ {collection_name}: Error - {e}")
    print()


def create_sample_data():
    """Create some sample data for testing"""
    db = get_database()
    
    # Sample user for testing (if doesn't exist)
    sample_user = {
        "_id": "507f1f77bcf86cd799439011",  # Fixed ObjectId for testing
        "email": "test@skinsense.com",
        "username": "testuser",
        "profile": {
            "age_range": "25_34",
            "skin_type": "combination",
            "gender": "female"
        },
        "created_at": datetime.utcnow()
    }
    
    # Insert sample user if not exists
    existing_user = db.users.find_one({"email": "test@skinsense.com"})
    if not existing_user:
        db.users.insert_one(sample_user)
        print("✓ Created sample test user")
    else:
        print("✓ Sample test user already exists")


def main():
    """Main initialization function"""
    try:
        print("🚀 Initializing SkinSense MongoDB Collections...")
        print("=" * 50)
        
        # Connect to MongoDB
        connect_to_mongo()
        print("✓ Connected to MongoDB")
        
        # Check current status
        check_collections()
        
        # Initialize goal templates and achievements
        print("📊 Setting up Goals service...")
        create_goal_templates()
        create_achievement_definitions()
        
        # Initialize routine templates
        print("🧴 Setting up Routines service...")
        create_routine_templates()
        
        # Create sample data
        print("🧪 Creating sample data...")
        create_sample_data()
        
        # Final status check
        print("\n🎉 Initialization Complete!")
        print("=" * 50)
        check_collections()
        
        print("\n📋 Summary:")
        print("✓ Goals service: Connected and initialized")
        print("✓ Routines service: Connected and initialized") 
        print("✓ MongoDB collections: Created with proper indexes")
        print("✓ Template data: Loaded for goals and routines")
        print("✓ Achievement system: Configured")
        print("✓ Sample data: Created for testing")
        
        print("\n🔗 Available Collections:")
        collections_info = {
            "goals": "User goals and progress tracking",
            "routines": "User skincare routines", 
            "goal_progress": "Historical goal progress data",
            "routine_completions": "Routine completion tracking",
            "achievements": "User achievements and badges",
            "goal_templates": "Pre-defined goal templates",
            "routine_templates": "Pre-defined routine templates"
        }
        
        for collection, description in collections_info.items():
            print(f"  • {collection}: {description}")
            
        print("\n🛠 Next Steps:")
        print("1. Start your FastAPI server: uvicorn app.main:app --reload")
        print("2. Test goal creation: POST /api/v1/goals/generate") 
        print("3. Test routine creation: POST /api/v1/routines/generate")
        print("4. Check the API documentation at: http://localhost:8000/docs")
        
    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        raise


if __name__ == "__main__":
    main()