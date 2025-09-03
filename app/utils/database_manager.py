"""
Database connection manager to eliminate redundant connection code
"""
import logging
from typing import Optional
from pymongo.database import Database
from app.database import get_database, connect_to_mongo

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Singleton database connection manager"""
    _instance: Optional[Database] = None
    _connection_attempts = 0
    MAX_RETRY_ATTEMPTS = 3
    
    @classmethod
    def get_database(cls) -> Database:
        """
        Get database connection with automatic retry logic.
        Returns existing connection if available, otherwise establishes new one.
        """
        if cls._instance is not None:
            return cls._instance
            
        # Try to get existing connection
        cls._instance = get_database()
        
        # If no connection, attempt to establish one
        if cls._instance is None:
            logger.warning("No database connection found, attempting to connect...")
            
            while cls._connection_attempts < cls.MAX_RETRY_ATTEMPTS:
                cls._connection_attempts += 1
                logger.info(f"Connection attempt {cls._connection_attempts}/{cls.MAX_RETRY_ATTEMPTS}")
                
                try:
                    connect_to_mongo()
                    cls._instance = get_database()
                    
                    if cls._instance is not None:
                        logger.info("Database connection established successfully")
                        cls._connection_attempts = 0  # Reset counter on success
                        return cls._instance
                        
                except Exception as e:
                    logger.error(f"Failed to connect to database: {e}")
                    
            # If all attempts failed
            raise RuntimeError(
                f"Failed to establish database connection after {cls.MAX_RETRY_ATTEMPTS} attempts"
            )
            
        return cls._instance
    
    @classmethod
    def ensure_connection(cls) -> Database:
        """
        Ensures a valid database connection exists.
        Alias for get_database() for clarity in usage.
        """
        return cls.get_database()
    
    @classmethod
    def reset_connection(cls) -> None:
        """
        Reset the connection (useful for testing or connection recovery).
        """
        cls._instance = None
        cls._connection_attempts = 0
        logger.info("Database connection reset")