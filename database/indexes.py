"""Create useful indexes on the existing MongoDB database."""

from __future__ import annotations

import logging

from database.connection import get_db

logger = logging.getLogger(__name__)


def ensure_indexes() -> None:
    db = get_db()
    if db is None:
        return
    try:
        db.users.create_index("email", unique=True)
        db.users.create_index("role")
        db.reports.create_index("public_id", unique=True)
        db.reports.create_index("user_id")
        db.reports.create_index("created_at")
        db.reports.create_index("status")
        db.reports.create_index("issue_group_id")
        db.reports.create_index([("latitude", 1), ("longitude", 1)])
        db.reports.create_index("location_name")
        logger.info("MongoDB indexes ensured on existing safestreet collections.")
    except Exception as exc:
        logger.warning("Could not create MongoDB indexes: %s", exc)
