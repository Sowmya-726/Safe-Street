from __future__ import annotations

import uuid
from datetime import datetime, timezone

from database.connection import get_db
from database.json_store import JsonStore
from services.civic import find_similar_reports, verification_summary

VALID_STATUSES = (
    "pending",
    "submitted",
    "under_review",
    "verified",
)

STATUS_LABELS = {
    "pending": "Submitted",
    "submitted": "Submitted",
    "verified": "Verified",
    "under_review": "Under Review",
}

ADMIN_TRANSITIONS = {
    "pending": ("under_review",),
    "submitted": ("under_review",),
    "under_review": ("verified",),
    "verified": (),
    "in_progress": ("under_review", "verified"),
    "resolved": ("under_review", "verified"),
    "reopened": ("under_review", "verified"),
}

VOTE_LABELS = {
    "still_present": "Yes, still present",
    "fixed": "No, it has been fixed",
    "not_sure": "Not sure",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def status_label(status: str | None) -> str:
    if not status:
        return "Submitted"
    key = str(status).lower()
    return STATUS_LABELS.get(key, str(status).replace("_", " ").title())


def severity_label(severity: str | None) -> str:
    key = str(severity or "").lower()
    return {
        "high": "High Priority",
        "medium": "Medium Priority",
        "low": "Low Priority",
    }.get(key, "Not assessed")


def format_report_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return str(iso)[:10]


def _public(doc: dict) -> dict:
    out = dict(doc)
    if "_id" in out:
        out["id"] = str(out["_id"])
        out.pop("_id", None)
    return out


def public_report(doc: dict | None) -> dict | None:
    """Fields safe to show on public pages (no user_id, email, or detections)."""
    if not doc:
        return None
    row = _public(doc) if "_id" in doc or "password_hash" in doc else dict(doc)
    summary = verification_summary(row)
    related = row.get("related_report_ids") or []
    return {
        "public_id": row.get("public_id"),
        "id": row.get("id"),
        "image": row.get("image"),
        "result_image": row.get("result_image"),
        "damage_type": row.get("damage_type") or "Road damage",
        "severity": row.get("severity"),
        "location_name": row.get("location_name") or "Location not specified",
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "description": row.get("description") or "",
        "status": row.get("status") or "pending",
        "created_at": row.get("created_at"),
        "date_label": format_report_date(row.get("created_at")),
        "status_label": status_label(row.get("status")),
        "severity_label": severity_label(row.get("severity")),
        "issue_group_id": row.get("issue_group_id"),
        "duplicate_of": row.get("duplicate_of"),
        "related_report_ids": related,
        "verification": summary,
        "reporter_label": "Community User",
        "distance_m": row.get("distance_m"),
        "distance_label": row.get("distance_label"),
        "hazard": row.get("hazard"),
    }


def admin_report(doc: dict | None) -> dict | None:
    if not doc:
        return None
    row = public_report(doc)
    raw = _public(doc)
    row["user_id"] = raw.get("user_id")
    row["status_history"] = raw.get("status_history") or []
    row["verification_votes"] = [
        {
            "vote": v.get("vote"),
            "created_at": v.get("created_at"),
            "date_label": format_report_date(v.get("created_at")),
        }
        for v in (raw.get("verification_votes") or [])
    ]
    return row


class ReportRepository:
    def __init__(self, json_store: JsonStore):
        self.json_store = json_store

    def _next_public_id(self) -> str:
        db = get_db()
        count = 0
        if db is not None:
            count = db.reports.count_documents({})
        else:
            count = len(self.json_store.load().get("reports", []))
        return f"RP{count + 1:03d}"

    def _write_mongo(self, public_id: str, updates: dict) -> dict | None:
        db = get_db()
        db.reports.update_one({"public_id": public_id}, {"$set": updates})
        doc = db.reports.find_one({"public_id": public_id})
        return _public(doc) if doc else None

    def _write_json(self, public_id: str, updates: dict) -> dict | None:
        data = self.json_store.load()
        for row in data["reports"]:
            if row.get("public_id") == public_id or row.get("id") == public_id:
                row.update(updates)
                self.json_store.save(data)
                return row
        return None

    def _save_fields(self, public_id: str, updates: dict) -> dict | None:
        db = get_db()
        if db is not None:
            return self._write_mongo(public_id, updates)
        return self._write_json(public_id, updates)

    def create(self, payload: dict) -> dict:
        group_id = payload.get("issue_group_id") or f"IG{uuid.uuid4().hex[:10]}"
        related = list(payload.get("related_report_ids") or [])
        duplicate_of = payload.get("duplicate_of")
        if duplicate_of and duplicate_of not in related:
            related.append(duplicate_of)
        doc = {
            "public_id": self._next_public_id(),
            "user_id": payload["user_id"],
            "image": payload.get("image"),
            "result_image": payload.get("result_image"),
            "damage_type": payload.get("damage_type"),
            "severity": payload.get("severity"),
            "confidence": payload.get("confidence"),
            "location_name": payload.get("location_name"),
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "description": payload.get("description", ""),
            "status": "pending",
            "detections": payload.get("detections") or [],
            "created_at": _now(),
            "issue_group_id": group_id,
            "duplicate_of": duplicate_of,
            "related_report_ids": related,
            "verification_votes": [],
            "verification_summary": {"still_present": 0, "fixed": 0, "not_sure": 0},
            "status_history": [
                {
                    "status": "pending",
                    "changed_at": _now(),
                    "changed_by": payload["user_id"],
                    "role": "user",
                    "reason": "Report submitted",
                }
            ],
        }
        db = get_db()
        if db is not None:
            result = db.reports.insert_one(doc)
            doc["id"] = str(result.inserted_id)
            if related:
                db.reports.update_many(
                    {"public_id": {"$in": related}},
                    {"$addToSet": {"related_report_ids": doc["public_id"]}},
                )
            return _public(doc)
        data = self.json_store.load()
        doc["id"] = uuid.uuid4().hex
        data["reports"].append(doc)
        for row in data["reports"]:
            if row.get("public_id") in related:
                ids = list(row.get("related_report_ids") or [])
                if doc["public_id"] not in ids:
                    ids.append(doc["public_id"])
                row["related_report_ids"] = ids
        self.json_store.save(data)
        return doc

    def list_for_user(self, user_id: str) -> list[dict]:
        db = get_db()
        if db is not None:
            rows = db.reports.find({"user_id": user_id}).sort("created_at", -1)
            return [_public(r) for r in rows]
        data = self.json_store.load()
        rows = [r for r in data["reports"] if r.get("user_id") == user_id]
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return rows

    def list_all(self) -> list[dict]:
        db = get_db()
        if db is not None:
            return [_public(r) for r in db.reports.find({}).sort("created_at", -1)]
        data = self.json_store.load()
        rows = list(data["reports"])
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return rows

    def list_group(self, issue_group_id: str) -> list[dict]:
        if not issue_group_id:
            return []
        db = get_db()
        if db is not None:
            return [_public(r) for r in db.reports.find({"issue_group_id": issue_group_id}).sort("created_at", -1)]
        data = self.json_store.load()
        return [r for r in data["reports"] if r.get("issue_group_id") == issue_group_id]

    def get_by_id(self, report_id: str) -> dict | None:
        db = get_db()
        if db is not None:
            from bson import ObjectId

            doc = db.reports.find_one({"public_id": report_id})
            if not doc:
                try:
                    doc = db.reports.find_one({"_id": ObjectId(report_id)})
                except Exception:
                    doc = None
            return _public(doc) if doc else None
        data = self.json_store.load()
        for row in data["reports"]:
            if row.get("id") == report_id or row.get("public_id") == report_id:
                return row
        return None

    def get_for_user(self, report_id: str, user_id: str) -> dict | None:
        db = get_db()
        if db is not None:
            from bson import ObjectId

            query = {"user_id": user_id}
            doc = db.reports.find_one({**query, "public_id": report_id})
            if not doc:
                try:
                    doc = db.reports.find_one({**query, "_id": ObjectId(report_id)})
                except Exception:
                    doc = None
            return _public(doc) if doc else None
        data = self.json_store.load()
        for row in data["reports"]:
            if row.get("user_id") == user_id and (
                row.get("id") == report_id or row.get("public_id") == report_id
            ):
                return row
        return None

    def similar_to(self, payload: dict) -> list[dict]:
        return find_similar_reports(payload, self.list_all())

    def add_verification(self, report_id: str, user_id: str, vote: str) -> tuple[dict | None, str | None]:
        if vote not in VOTE_LABELS:
            return None, "Choose a verification option."
        row = self.get_by_id(report_id)
        if not row:
            return None, "Report not found."
        votes = list(row.get("verification_votes") or [])
        if any(v.get("user_id") == user_id for v in votes):
            return None, "You have already verified this issue."
        votes.append({"user_id": user_id, "vote": vote, "created_at": _now()})
        summary = {"still_present": 0, "fixed": 0, "not_sure": 0}
        for item in votes:
            key = item.get("vote")
            if key in summary:
                summary[key] += 1
        updated = self._save_fields(
            row["public_id"],
            {"verification_votes": votes, "verification_summary": summary},
        )
        return updated, None

    def user_has_verified(self, row: dict, user_id: str | None) -> bool:
        if not user_id:
            return False
        return any(v.get("user_id") == user_id for v in (row.get("verification_votes") or []))

    def append_status(
        self,
        report_id: str,
        status: str,
        admin_id: str,
        reason: str,
        extra: dict | None = None,
    ) -> tuple[dict | None, str | None]:
        if status == "submitted":
            status = "pending"
        if status not in VALID_STATUSES:
            return None, "Invalid status."
        row = self.get_by_id(report_id)
        if not row:
            return None, "Report not found."
        current = row.get("status") or "pending"
        allowed = ADMIN_TRANSITIONS.get(current, ())
        if status != current and status not in allowed:
            return None, f"Cannot change status from {status_label(current)} to {status_label(status)}."
        history = list(row.get("status_history") or [])
        history.append(
            {
                "status": status,
                "changed_at": _now(),
                "changed_by": admin_id,
                "role": "admin",
                "reason": (reason or "").strip() or "Status updated by administrator",
            }
        )
        updates = {"status": status, "status_history": history}
        if extra:
            updates.update(extra)
        return self._save_fields(row["public_id"], updates), None

    def stats_for_user(self, user_id: str) -> dict:
        rows = self.list_for_user(user_id)
        return summarize_reports(rows)

    def stats_all(self) -> dict:
        return summarize_reports(self.list_all())


def summarize_reports(rows: list[dict]) -> dict:
    total = len(rows)
    today = datetime.now(timezone.utc).date().isoformat()
    reported_today = sum(1 for r in rows if str(r.get("created_at") or "").startswith(today))
    pending = sum(1 for r in rows if r.get("status") in ("pending", "submitted", None, ""))
    review = sum(1 for r in rows if r.get("status") == "under_review")
    verified = sum(1 for r in rows if r.get("status") == "verified")
    community_votes = sum(int((verification_summary(r) or {}).get("total") or 0) for r in rows)
    high = sum(1 for r in rows if str(r.get("severity", "")).lower() == "high")
    medium = sum(1 for r in rows if str(r.get("severity", "")).lower() == "medium")
    low = sum(1 for r in rows if str(r.get("severity", "")).lower() == "low")
    damaged = sum(1 for r in rows if r.get("damage_type") and r.get("damage_type") != "Undetected")
    inspected = len(
        {
            (r.get("location_name"), r.get("latitude"), r.get("longitude"))
            for r in rows
            if r.get("location_name") or r.get("latitude") is not None
        }
    )
    types: dict[str, int] = {}
    areas: dict[str, int] = {}
    groups = {r.get("issue_group_id") for r in rows if r.get("issue_group_id")}
    still = sum(int((r.get("verification_summary") or {}).get("still_present") or 0) for r in rows)
    fixed = sum(int((r.get("verification_summary") or {}).get("fixed") or 0) for r in rows)
    by_day: dict[str, int] = {}
    for row in rows:
        label = row.get("damage_type") or "Unknown"
        types[label] = types.get(label, 0) + 1
        place = row.get("location_name") or "Unspecified"
        areas[place] = areas.get(place, 0) + 1
        day = str(row.get("created_at") or "")[:10]
        if day:
            by_day[day] = by_day.get(day, 0) + 1
    return {
        "total": total,
        "reported_today": reported_today,
        "pending": pending,
        "under_review": review,
        "review_only": review,
        "verified": verified,
        "community_votes": community_votes,
        "high": high,
        "medium": medium,
        "low": low,
        "damaged": damaged,
        "inspected": inspected or total,
        "types": types,
        "areas": dict(sorted(areas.items(), key=lambda kv: kv[1], reverse=True)[:20]),
        "groups": len(groups),
        "verification_still": still,
        "verification_fixed": fixed,
        "statuses": {
            "pending": pending,
            "under_review": review,
            "verified": verified,
        },
        "by_day": dict(sorted(by_day.items())),
    }
