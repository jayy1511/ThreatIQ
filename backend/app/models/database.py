from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class Database:
    """MongoDB database manager."""
    
    client: AsyncIOMotorClient = None
    db = None
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB."""
        try:
            cls.client = AsyncIOMotorClient(settings.mongodb_uri)
            cls.db = cls.client[settings.mongodb_db_name]
            
            await cls.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {settings.mongodb_db_name}")
            
            await cls.create_indexes()
            
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection."""
        if cls.client:
            cls.client.close()
            logger.info("Closed MongoDB connection")
    
    @classmethod
    async def create_indexes(cls):
        """Create database indexes for performance."""
        try:
            await cls.db.user_profiles.create_index("user_id", unique=True)
            # Interactions collection indexes
            await cls.db.interactions.create_index([("user_id", 1), ("timestamp", -1)])
            # Unique index on (user_id, request_id) for idempotency
            await cls.db.interactions.create_index(
                [("user_id", 1), ("request_id", 1)], 
                unique=True,
                name="unique_user_request"
            )
            
            await cls.db.users.create_index("firebase_uid", unique=True)
            
            # OAuth state collection: unique on state value, TTL auto-expires documents
            await cls.db.oauth_states.create_index("state", unique=True)
            await cls.db.oauth_states.create_index(
                "expires_at",
                expireAfterSeconds=0,
                name="oauth_state_ttl"
            )
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    @classmethod
    def get_db(cls):
        """Get database instance."""
        return cls.db


async def get_database():
    """Dependency to get database instance."""
    return Database.get_db()
