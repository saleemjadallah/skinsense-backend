"""
Database Index Setup for Product Image Cache
Creates TTL index to automatically expire cached product images after 7 days

Run with: python -m scripts.setup_product_image_cache_index
"""

import logging
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient, ASCENDING
from pymongo.errors import OperationFailure

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_product_image_cache_index():
    """
    Create TTL index on product_image_cache collection.

    This index automatically removes documents when expires_at is reached,
    preventing stale image URLs from accumulating in the database.
    """
    try:
        # Connect to MongoDB
        client = MongoClient(settings.MONGODB_URL)
        db = client.get_database()

        collection_name = "product_image_cache"
        collection = db[collection_name]

        logger.info(f"Setting up indexes for {collection_name} collection...")

        # 1. TTL Index on expires_at (auto-delete expired entries)
        logger.info("Creating TTL index on expires_at field...")
        collection.create_index(
            [("expires_at", ASCENDING)],
            name="expires_at_ttl",
            expireAfterSeconds=0,  # Delete immediately when expires_at is reached
            background=True
        )
        logger.info("✓ TTL index created")

        # 2. Unique index on product_url (prevent duplicates)
        logger.info("Creating unique index on product_url field...")
        collection.create_index(
            [("product_url", ASCENDING)],
            name="product_url_unique",
            unique=True,
            background=True
        )
        logger.info("✓ Unique index created")

        # 3. Compound index for efficient lookups
        logger.info("Creating compound index for cache lookups...")
        collection.create_index(
            [("product_url", ASCENDING), ("expires_at", ASCENDING)],
            name="product_url_expires_at",
            background=True
        )
        logger.info("✓ Compound index created")

        # Verify indexes
        indexes = list(collection.list_indexes())
        logger.info(f"\n✓ Successfully created {len(indexes)} indexes for {collection_name}:")
        for idx in indexes:
            logger.info(f"  - {idx['name']}: {idx.get('key', {})}")

        # Clean up any existing expired entries
        result = collection.delete_many({"expires_at": {"$lt": "now"}})
        logger.info(f"\n✓ Cleaned up {result.deleted_count} expired cache entries")

        logger.info("\n✅ Product image cache indexes setup complete!")

        client.close()
        return True

    except OperationFailure as e:
        logger.error(f"MongoDB operation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to setup indexes: {e}", exc_info=True)
        return False


def verify_setup():
    """Verify that indexes were created correctly"""
    try:
        client = MongoClient(settings.MONGODB_URL)
        db = client.get_database()
        collection = db["product_image_cache"]

        indexes = {idx['name']: idx for idx in collection.list_indexes()}

        required_indexes = [
            "expires_at_ttl",
            "product_url_unique",
            "product_url_expires_at"
        ]

        logger.info("\n🔍 Verifying index setup...")
        all_present = True

        for idx_name in required_indexes:
            if idx_name in indexes:
                logger.info(f"  ✓ {idx_name} - present")
            else:
                logger.error(f"  ✗ {idx_name} - MISSING")
                all_present = False

        client.close()

        if all_present:
            logger.info("\n✅ All required indexes are present!")
        else:
            logger.error("\n❌ Some indexes are missing!")

        return all_present

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Product Image Cache - Database Index Setup")
    logger.info("=" * 60)

    # Setup indexes
    success = setup_product_image_cache_index()

    if success:
        # Verify setup
        verify_success = verify_setup()

        if verify_success:
            logger.info("\n🎉 Setup completed successfully!")
            sys.exit(0)
        else:
            logger.error("\n⚠️  Setup completed but verification failed")
            sys.exit(1)
    else:
        logger.error("\n❌ Setup failed!")
        sys.exit(1)
