"""MongoDB connection. Credentials come from environment variables only."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_client = None
_db = None
_mongo_error: str | None = None


def mongo_status() -> dict[str, Any]:
    return {
        "connected": _db is not None,
        "error": _mongo_error,
        "database": os.getenv("MONGODB_DB", "safestreet"),
    }


def get_db():
    """Return a pymongo database or None if MongoDB is not configured/reachable."""
    global _client, _db, _mongo_error
    if _db is not None:
        return _db
    # A failed ping is remembered for this process so repositories do not each
    # wait on serverSelectionTimeoutMS (the site becomes very slow otherwise).
    if _mongo_error is not None:
        return None

    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        _mongo_error = "MONGODB_URI is not set. MongoDB is required for Safe Street storage."
        logger.warning(_mongo_error)
        return None

    try:
        from pymongo import MongoClient

        _client = MongoClient(uri, serverSelectionTimeoutMS=4000)
        _client.admin.command("ping")
        name = os.getenv("MONGODB_DB", "safestreet")
        _db = _client[name]
        _mongo_error = None
        logger.info("Connected to MongoDB database %s", name)
        return _db
    except Exception as exc:
        _mongo_error = (
            f"MongoDB unavailable ({exc}). "
            "Safe Street expects MongoDB at MONGODB_URI; start MongoDB and restart the app."
        )
        logger.warning(_mongo_error)
        _client = None
        _db = None
        return None
