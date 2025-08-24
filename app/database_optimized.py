from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from app.core.config import settings
import logging
import certifi
import time

logger = logging.getLogger(__name__)

class OptimizedDatabase:
    """Optimized MongoDB connection with better pooling and performance"""
    client: MongoClient = None
    database = None

db = OptimizedDatabase()

def connect_to_mongo_optimized():
    """Create optimized database connection for better performance"""
    max_retries = 2  # Reduced retries for faster failover
    retry_delay = 1   # Shorter initial delay
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Connecting to MongoDB (optimized, attempt {attempt + 1}/{max_retries})...")
            
            # MongoDB Atlas optimized connection
            if "mongodb+srv://" in settings.MONGODB_URL:
                logger.info("Configuring optimized MongoDB Atlas connection")
                
                # Build optimized connection string
                base_url = settings.MONGODB_URL.split("?")[0]
                
                # Optimized parameters for faster connections
                params = [
                    "retryWrites=true",
                    "w=majority",
                    "maxPoolSize=100",           # Increased pool size
                    "minPoolSize=20",            # Higher minimum connections
                    "maxIdleTimeMS=120000",      # Keep connections alive longer
                    "waitQueueTimeoutMS=5000",   # Shorter queue timeout
                    "serverSelectionTimeoutMS=5000",  # Faster server selection
                    "connectTimeoutMS=10000",    # Faster initial connect
                    "socketTimeoutMS=20000",     # Reasonable socket timeout
                    "compressors=zstd,snappy,zlib",  # Enable compression
                    "zlibCompressionLevel=6",    # Compression level
                ]
                
                connection_url = f"{base_url}?{'&'.join(params)}"
                
                # Create optimized client
                db.client = MongoClient(
                    connection_url,
                    serverSelectionTimeoutMS=5000,   # Override for faster selection
                    connectTimeoutMS=10000,
                    socketTimeoutMS=20000,
                    maxPoolSize=100,                 # Large connection pool
                    minPoolSize=20,                  # Keep minimum connections ready
                    maxIdleTimeMS=120000,            # 2 minutes idle time
                    waitQueueTimeoutMS=5000,
                    retryWrites=True,
                    retryReads=True,
                    w='majority',
                    journal=True,                    # Ensure write durability
                    tls=True,
                    tlsCAFile=certifi.where(),
                    # Connection pool monitoring
                    maxConnecting=10,                # Max concurrent connection attempts
                    heartbeatFrequencyMS=10000,     # More frequent heartbeats
                    localThresholdMS=15,            # Tighter latency threshold
                )
            else:
                # Local MongoDB optimized
                logger.info("Configuring optimized local MongoDB connection")
                db.client = MongoClient(
                    settings.MONGODB_URL,
                    serverSelectionTimeoutMS=3000,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=10000,
                    maxPoolSize=50,
                    minPoolSize=10,
                    maxIdleTimeMS=60000,
                )
            
            # Extract database name
            if "mongodb.net/" in settings.MONGODB_URL:
                db_name = settings.MONGODB_URL.split("/")[-1].split("?")[0] or "skinpal"
            else:
                db_name = settings.DATABASE_NAME or "skinpal"
            
            logger.info(f"Using database: {db_name}")
            db.database = db.client[db_name]
            
            # Test connection with short timeout
            db.client.admin.command('ping', maxTimeMS=3000)
            logger.info("✓ Connected to MongoDB (optimized)")
            
            # Warm up connection pool
            warm_up_connections()
            
            return
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Slightly increase delay
            else:
                logger.error(f"Failed to connect after {max_retries} attempts")
                raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

def warm_up_connections():
    """Pre-warm the connection pool for faster initial requests"""
    try:
        # Run lightweight queries to establish connections
        collections = ['users', 'routines', 'goals', 'skin_analyses']
        for collection in collections:
            db.database[collection].find_one({}, {"_id": 1})
        logger.info("✓ Connection pool warmed up")
    except Exception as e:
        logger.warning(f"Could not warm up connections: {e}")

def get_database_optimized():
    """Get optimized database instance"""
    if db.database is None:
        connect_to_mongo_optimized()
    return db.database

# Ensure indexes exist for optimal query performance
def ensure_optimal_indexes():
    """Create compound indexes for common query patterns"""
    try:
        # Homepage data queries - compound indexes for better performance
        db.database.routines.create_index(
            [("user_id", 1), ("is_active", 1), ("type", 1)],
            name="homepage_routines_idx"
        )
        
        db.database.goals.create_index(
            [("user_id", 1), ("status", 1), ("target_date", 1)],
            name="homepage_goals_idx"
        )
        
        db.database.skin_analyses.create_index(
            [("user_id", 1), ("created_at", -1)],
            name="homepage_analyses_idx"
        )
        
        # Add hint optimizer for frequently used queries
        db.database.routine_completions.create_index(
            [("user_id", 1), ("routine_id", 1), ("completed_at", -1)],
            name="completions_composite_idx"
        )
        
        logger.info("✓ Optimal indexes created")
    except Exception as e:
        logger.error(f"Error creating optimal indexes: {e}")