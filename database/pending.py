"""Server-side draft detections. Flask cookies are too small for this payload."""

from __future__ import annotations

from database.connection import get_db
from database.json_store import JsonStore


class PendingDetectionStore:
    def __init__(self, json_store: JsonStore):
        self.json_store = json_store

    def set(self, user_id: str, payload: dict) -> None:
        db = get_db()
        if db is not None:
            db.pending_detections.replace_one(
                {"user_id": user_id},
                {"user_id": user_id, **payload},
                upsert=True,
            )
            return
        data = self.json_store.load()
        data["pending"][user_id] = payload
        self.json_store.save(data)

    def get(self, user_id: str) -> dict:
        db = get_db()
        if db is not None:
            doc = db.pending_detections.find_one({"user_id": user_id}) or {}
            doc.pop("_id", None)
            doc.pop("user_id", None)
            return doc
        return dict(self.json_store.load().get("pending", {}).get(user_id) or {})

    def clear(self, user_id: str) -> None:
        db = get_db()
        if db is not None:
            db.pending_detections.delete_one({"user_id": user_id})
            return
        data = self.json_store.load()
        data.get("pending", {}).pop(user_id, None)
        self.json_store.save(data)
