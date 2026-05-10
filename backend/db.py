"""
Database Connection Module
--------------------------

Provides a global async MongoDB client + database accessor.
Used by:
- analytics logging
- Retell webhook router
- conversational router
- patient lookup + registration
- appointment booking
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection string (Railway or local)
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")

if not MONGO_URI:
    raise RuntimeError("Missing MONGO_URI environment variable")

# Create global client
_client = AsyncIOMotorClient(MONGO_URI)

# Select database (default: 'dental_ai')
DB_NAME = os.getenv("MONGO_DB_NAME", "dental_ai")
_db = _client[DB_NAME]


def get_db():
    """
    Returns the active MongoDB database instance.
    This is intentionally simple and stable.
    """
    return _db
