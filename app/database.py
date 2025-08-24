from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from app.core.config import settings
import logging
import certifi
import ssl
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import time

logger = logging.getLogger(__name__)

class Database:
    client: MongoClient = None
    database = None

db = Database()

def _add_connection_params(url: str) -> str:
    """Add necessary connection parameters to MongoDB URL"""
    try:
        # Parse the existing URL
        if "mongodb+srv://" in url:
            # For SRV URLs, we need to handle them specially
            # Split by ? to get base URL and existing params
            if "?" in url:
                base_url, params_str = url.split("?", 1)
                # Parse existing parameters
                existing_params = {}
                for param in params_str.split("&"):
                    if "=" in param:
                        key, value = param.split("=", 1)
                        existing_params[key] = value
            else:
                base_url = url
                existing_params = {}
            
            # Add or update required parameters
            required_params = {
                'retryWrites': 'true',
                'w': 'majority',
                'tlsDisableOCSPEndpointCheck': 'true',  # Critical for SSL issues
                'tlsAllowInvalidHostnames': 'false',
                'maxPoolSize': '50',
                'minPoolSize': '10',
                'maxIdleTimeMS': '45000'
            }
            
            # Merge parameters (existing params take precedence)
            for key, value in required_params.items():
                if key not in existing_params:
                    existing_params[key] = value
            
            # Reconstruct URL
            if existing_params:
                params_str = "&".join([f"{k}={v}" for k, v in existing_params.items()])
                return f"{base_url}?{params_str}"
            else:
                return base_url
        else:
            # For non-SRV URLs, return as-is
            return url
    except Exception as e:
        logger.warning(f"Error parsing MongoDB URL: {e}, using original URL")
        return url

def _extract_database_name(url: str, default_name: str) -> str:
    """Extract database name from MongoDB URL or use default"""
    try:
        # For MongoDB Atlas URLs like mongodb+srv://...@cluster.mongodb.net/dbname?params
        if "mongodb.net/" in url:
            # Split by ? to remove parameters
            url_without_params = url.split("?")[0]
            # Split by / and get the last part
            parts = url_without_params.split("/")
            if len(parts) > 3 and parts[-1]:
                db_name = parts[-1]
                if db_name and db_name != "test":  # Avoid using 'test' database
                    return db_name
        
        # For standard MongoDB URLs like mongodb://host:port/dbname
        if "mongodb://" in url:
            url_without_params = url.split("?")[0]
            parts = url_without_params.split("/")
            if len(parts) > 3 and parts[-1]:
                db_name = parts[-1]
                if db_name and db_name != "test":
                    return db_name
        
        return default_name
    except Exception as e:
        logger.warning(f"Error extracting database name: {e}, using default: {default_name}")
        return default_name

def get_database():
    """Get database instance"""
    return db.database

def connect_to_mongo():
    """Create database connection with retry logic"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Connecting to MongoDB (attempt {attempt + 1}/{max_retries})...")
            
            # Check if this is MongoDB Atlas (srv) or local MongoDB
            if "mongodb+srv://" in settings.MONGODB_URL:
                # MongoDB Atlas connection with SSL
                logger.info("Detected MongoDB Atlas connection")
                
                # Properly parse and modify the connection URL
                connection_url = _add_connection_params(settings.MONGODB_URL)
                logger.info(f"Connecting with optimized parameters")
                
                # MongoDB Atlas connection with proper SSL handling
                db.client = MongoClient(
                    connection_url,
                    serverSelectionTimeoutMS=15000,  # Increased timeout
                    connectTimeoutMS=30000,          # Increased timeout
                    socketTimeoutMS=30000,           # Increased timeout
                    maxPoolSize=50,                  # Connection pooling
                    minPoolSize=10,
                    maxIdleTimeMS=45000,
                    waitQueueTimeoutMS=10000,
                    retryWrites=True,
                    retryReads=True,
                    w='majority',                    # Write concern
                    tls=True,                        # Explicitly enable TLS
                    tlsCAFile=certifi.where(),       # Use certifi certificates
                    tlsAllowInvalidHostnames=False   # Keep hostname validation
                )
            else:
                # Local MongoDB connection
                logger.info("Detected local MongoDB connection")
                db.client = MongoClient(
                    settings.MONGODB_URL,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=10000,
                    maxPoolSize=20,
                    minPoolSize=5
                )
            
            # Extract database name properly
            database_name = _extract_database_name(settings.MONGODB_URL, settings.DATABASE_NAME)
            logger.info(f"Using database: {database_name}")
            
            db.database = db.client[database_name]
            
            # Test connection with timeout
            db.client.admin.command('ping', maxTimeMS=5000)
            logger.info("✓ Connected to MongoDB successfully")
            
            # Create indexes
            create_indexes()
            
            return  # Success, exit the function
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Failed to connect to MongoDB after {max_retries} attempts")
                raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            raise

def close_mongo_connection():
    """Close database connection"""
    if db.client:
        db.client.close()
        logger.info("Disconnected from MongoDB")

def create_indexes():
    """Create database indexes for performance"""
    try:
        # User indexes
        db.database.users.create_index("email", unique=True)
        db.database.users.create_index("username")  # Not unique - usernames can be duplicate
        
        # Skin analysis indexes
        db.database.skin_analyses.create_index([("user_id", 1), ("created_at", -1)])
        db.database.skin_analyses.create_index("user_id")
        
        # Product indexes
        db.database.products.create_index("barcode", unique=True, sparse=True)
        db.database.products.create_index("name")
        db.database.products.create_index("brand")
        
        # Community post indexes
        db.database.community_posts.create_index([("created_at", -1)])
        db.database.community_posts.create_index("user_id")
        
        # Recommendation cache indexes
        db.database.recommendation_cache.create_index([("user_id", 1), ("expires_at", 1)])
        db.database.recommendation_cache.create_index("expires_at", expireAfterSeconds=0)
        
        # User product interaction indexes
        db.database.user_product_interactions.create_index([("user_id", 1), ("created_at", -1)])
        db.database.user_product_interactions.create_index([("user_id", 1), ("interaction_type", 1)])
        
        # Goals indexes
        db.database.goals.create_index([("user_id", 1), ("status", 1), ("created_at", -1)])
        db.database.goals.create_index([("user_id", 1), ("type", 1)])
        db.database.goals.create_index([("user_id", 1), ("target_date", 1)])
        db.database.goals.create_index("status")
        db.database.goals.create_index("target_parameter")
        
        # Goal progress indexes
        db.database.goal_progress.create_index([("goal_id", 1), ("recorded_at", -1)])
        db.database.goal_progress.create_index([("user_id", 1), ("recorded_at", -1)])
        db.database.goal_progress.create_index("source")
        
        # Achievements indexes
        db.database.achievements.create_index([("user_id", 1), ("unlocked", 1)])
        db.database.achievements.create_index("achievement_id")
        db.database.achievements.create_index([("user_id", 1), ("category", 1)])
        
        # Goal templates indexes
        db.database.goal_templates.create_index("category")
        db.database.goal_templates.create_index("type")
        db.database.goal_templates.create_index([("usage_count", -1)])
        
        # Routines indexes
        db.database.routines.create_index([("user_id", 1), ("type", 1)])
        db.database.routines.create_index([("user_id", 1), ("is_active", 1), ("created_at", -1)])
        db.database.routines.create_index([("user_id", 1), ("is_favorite", 1)])
        db.database.routines.create_index("created_from")
        db.database.routines.create_index("target_concerns")
        
        # Routine completions indexes
        db.database.routine_completions.create_index([("user_id", 1), ("completed_at", -1)])
        db.database.routine_completions.create_index([("routine_id", 1), ("completed_at", -1)])
        db.database.routine_completions.create_index([("user_id", 1), ("routine_id", 1), ("completed_at", -1)])
        
        # Routine templates indexes
        db.database.routine_templates.create_index("type")
        db.database.routine_templates.create_index("target_concerns")
        db.database.routine_templates.create_index("suitable_for_skin_types")
        db.database.routine_templates.create_index([("popularity_score", -1)])
        
        # Daily insights indexes
        db.database.daily_insights.create_index([("user_id", 1), ("generated_for_date", 1)])
        db.database.daily_insights.create_index("expires_at", expireAfterSeconds=0)
        db.database.daily_insights.create_index([("user_id", 1), ("viewed", 1)])
        
        # Plans indexes
        db.database.plans.create_index([("user_id", 1), ("status", 1)])
        db.database.plans.create_index([("user_id", 1), ("created_at", -1)])
        db.database.plans.create_index("plan_type")
        db.database.plans.create_index("status")
        db.database.plans.create_index([("user_id", 1), ("plan_type", 1)])
        
        # Plan progress indexes
        db.database.plan_progress.create_index([("plan_id", 1), ("week_number", -1)])
        db.database.plan_progress.create_index([("user_id", 1), ("recorded_at", -1)])
        db.database.plan_progress.create_index([("plan_id", 1), ("user_id", 1)])
        
        # Plan templates indexes
        db.database.plan_templates.create_index("plan_type")
        db.database.plan_templates.create_index("suitable_for_concerns")
        db.database.plan_templates.create_index("suitable_for_skin_types")
        db.database.plan_templates.create_index([("usage_count", -1)])
        db.database.plan_templates.create_index([("user_rating", -1)])
        
        logger.info("Database indexes created successfully")
        
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")