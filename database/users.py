from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from database.connection import get_db
from database.json_store import JsonStore

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_admin_user(doc: dict | None) -> bool:
    if not doc:
        return False
    if doc.get("role") == "admin":
        return True
    return bool(doc.get("is_admin"))


def public_user(doc: dict | None) -> dict | None:
    if not doc:
        return None
    out = dict(doc)
    out.pop("password_hash", None)
    if "_id" in out:
        out["id"] = str(out["_id"])
        out.pop("_id", None)
    out["is_admin"] = is_admin_user(out)
    out["role"] = "admin" if out["is_admin"] else (out.get("role") or "user")
    return out


class UserRepository:
    def __init__(self, json_store: JsonStore):
        self.json_store = json_store

    def create(self, name: str, email: str, password_hash: str, role: str = "user") -> dict:
        db = get_db()
        role = "admin" if role == "admin" else "user"
        doc = {
            "name": name.strip(),
            "email": email.strip().lower(),
            "password_hash": password_hash,
            "created_at": _now(),
            "is_admin": role == "admin",
            "role": role,
        }
        if db is not None:
            result = db.users.insert_one(doc)
            doc["id"] = str(result.inserted_id)
            return public_user(doc)
        data = self.json_store.load()
        doc["id"] = uuid.uuid4().hex
        data["users"].append(doc)
        self.json_store.save(data)
        return public_user(doc)

    def find_by_email(self, email: str) -> dict | None:
        email = email.strip().lower()
        db = get_db()
        if db is not None:
            doc = db.users.find_one({"email": email})
            if doc:
                doc = dict(doc)
                doc["id"] = str(doc["_id"])
                return doc
        data = self.json_store.load()
        for user in data.get("users", []):
            if user.get("email") == email:
                found = dict(user)
                found["id"] = str(found.get("id") or "")
                return found
        return None

    def find_by_id(self, user_id: str) -> dict | None:
        if user_id is None or str(user_id).strip() == "":
            return None
        user_id = str(user_id)
        db = get_db()
        if db is not None:
            from bson import ObjectId
            from bson.errors import InvalidId

            doc = None
            try:
                doc = db.users.find_one({"_id": ObjectId(user_id)})
            except (InvalidId, Exception):
                doc = None
            if not doc:
                doc = db.users.find_one({"id": user_id})
            if doc:
                doc = dict(doc)
                doc["id"] = str(doc.get("_id") or doc.get("id"))
                return doc
        data = self.json_store.load()
        for user in data.get("users", []):
            if str(user.get("id")) == user_id:
                return dict(user)
        return None

    def update_profile(self, user_id: str, name: str) -> dict | None:
        db = get_db()
        if db is not None:
            from bson import ObjectId

            db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"name": name.strip()}})
            return public_user(self.find_by_id(user_id))
        data = self.json_store.load()
        for user in data["users"]:
            if user.get("id") == user_id:
                user["name"] = name.strip()
                self.json_store.save(data)
                return public_user(user)
        return None

    def update_password(self, user_id: str, password_hash: str) -> bool:
        db = get_db()
        if db is not None:
            from bson import ObjectId

            result = db.users.update_one(
                {"_id": ObjectId(user_id)}, {"$set": {"password_hash": password_hash}}
            )
            return result.matched_count == 1
        data = self.json_store.load()
        for user in data["users"]:
            if user.get("id") == user_id:
                user["password_hash"] = password_hash
                self.json_store.save(data)
                return True
        return False

    def set_role(self, user_id: str, role: str) -> dict | None:
        role = "admin" if role == "admin" else "user"
        updates = {"role": role, "is_admin": role == "admin"}
        db = get_db()
        if db is not None:
            from bson import ObjectId

            db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
            return public_user(self.find_by_id(user_id))
        data = self.json_store.load()
        for user in data["users"]:
            if user.get("id") == user_id:
                user.update(updates)
                self.json_store.save(data)
                return public_user(user)
        return None

    def any_admin(self) -> bool:
        db = get_db()
        if db is not None:
            return db.users.find_one({"$or": [{"role": "admin"}, {"is_admin": True}]}) is not None
        data = self.json_store.load()
        return any(is_admin_user(user) for user in data.get("users", []))


def ensure_initial_admin(json_store: JsonStore) -> None:
    """Ensure the configured admin account exists. Does not expose credentials."""
    users = UserRepository(json_store)
    email = (os.getenv("ADMIN_EMAIL") or "").strip()
    password = os.getenv("ADMIN_PASSWORD") or ""
    if not email or not password:
        if not users.any_admin():
            logger.warning("No administrator account exists. Set ADMIN_EMAIL and ADMIN_PASSWORD to create one.")
        return
    existing = users.find_by_email(email)
    if existing:
        if not is_admin_user(existing):
            users.set_role(existing["id"], "admin")
            logger.info("Granted administrator role to the configured account.")
        return
    from safe_street.auth import hash_password

    users.create("Safe Street Admin", email, hash_password(password), role="admin")
    logger.info("Created the initial administrator account.")
