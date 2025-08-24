import sys
from pathlib import Path
from datetime import datetime
from bson import ObjectId

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_database, close_mongo_connection, connect_to_mongo


def verify_collections():
    """Verify all MongoDB collections are properly set up"""
    try:
        connect_to_mongo()
        db = get_database()
        print("Verifying MongoDB Collections Setup...\n")
        
        # Define expected collections
        expected_collections = {
            # User Management
            "users": "User accounts and profiles",
            
            # Skin Analysis
            "skin_analyses": "Skin analysis results from ORBO AI",
            
            # Routine Management
            "routines": "User skincare routines",
            "routine_completions": "Routine completion tracking",
            "routine_templates": "Pre-defined routine templates",
            
            # Goal Management
            "goals": "User goals and targets",
            "goal_progress": "Goal progress tracking",
            "achievements": "User achievements and badges",
            "goal_templates": "Pre-defined goal templates",
            
            # Products
            "products": "Product database",
            "product_interactions": "User product interactions",
            
            # Community
            "community_posts": "Community forum posts",
            "post_comments": "Comments on posts",
            
            # Notifications
            "notifications": "User notifications",
            
            # Cache
            "recommendation_cache": "Cached AI recommendations"
        }
        
        # Get existing collections
        existing_collections = db.list_collection_names()
        
        print("Collection Status:")
        print("=" * 60)
        print(f"{'Collection':<25} {'Status':<10} {'Documents':<10} {'Description'}")
        print("=" * 60)
        
        all_good = True
        
        for collection, description in expected_collections.items():
            if collection in existing_collections:
                count = db[collection].count_documents({})
                status = "✓ EXISTS"
                print(f"{collection:<25} {status:<10} {count:<10} {description}")
            else:
                status = "✗ MISSING"
                print(f"{collection:<25} {status:<10} {'N/A':<10} {description}")
                all_good = False
        
        # Check for unexpected collections
        print("\nOther Collections Found:")
        print("-" * 60)
        for collection in existing_collections:
            if collection not in expected_collections and not collection.startswith('system.'):
                count = db[collection].count_documents({})
                print(f"{collection:<25} {count} documents")
        
        # Verify indexes on critical collections
        print("\nIndex Verification:")
        print("=" * 60)
        
        critical_indexes = {
            "users": ["email", "username"],
            "routines": ["user_id", "is_active"],
            "goals": ["user_id", "status"],
            "skin_analyses": ["user_id", "created_at"]
        }
        
        for collection, expected_indexes in critical_indexes.items():
            if collection in existing_collections:
                indexes = db[collection].index_information()
                index_fields = []
                for index_name, index_info in indexes.items():
                    if index_name != "_id_":
                        keys = index_info.get('key', [])
                        for field, _ in keys:
                            index_fields.append(field)
                
                print(f"\n{collection}:")
                for field in expected_indexes:
                    if field in index_fields:
                        print(f"  ✓ Index on '{field}' exists")
                    else:
                        print(f"  ✗ Index on '{field}' MISSING")
                        all_good = False
        
        # Summary
        print("\n" + "=" * 60)
        if all_good:
            print("✅ All collections and critical indexes are properly set up!")
        else:
            print("⚠️  Some collections or indexes are missing. Run init_collections.py to fix.")
        
        # Sample data check
        print("\nSample Data Check:")
        print("-" * 60)
        
        # Check for routine templates
        routine_template_count = db.routine_templates.count_documents({})
        print(f"Routine Templates: {routine_template_count} (Run init_routine_templates.py if 0)")
        
        # Check for goal templates
        goal_template_count = db.goal_templates.count_documents({})
        print(f"Goal Templates: {goal_template_count} (Run init_goal_templates.py if 0)")
        
    except Exception as e:
        print(f"\n❌ Error verifying collections: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        close_mongo_connection()


if __name__ == "__main__":
    print("SkinSense AI - MongoDB Collections Verification")
    print("=" * 50)
    verify_collections()