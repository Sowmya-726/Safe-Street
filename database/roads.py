"""Placeholder roads collection for a future admin/road-segment layer."""

from __future__ import annotations

from database.connection import get_db
from database.json_store import JsonStore


def upsert_road_from_report(report: dict, json_store: JsonStore | None = None) -> None:
    if report.get("latitude") is None or report.get("longitude") is None:
        return
    payload = {
        "latitude": report.get("latitude"),
        "longitude": report.get("longitude"),
        "location_name": report.get("location_name"),
        "last_damage_type": report.get("damage_type"),
        "last_severity": report.get("severity"),
        "last_report_id": report.get("public_id"),
        "updated_at": report.get("created_at"),
    }
    db = get_db()
    if db is not None:
        db.roads.update_one(
            {
                "latitude": payload["latitude"],
                "longitude": payload["longitude"],
                "location_name": payload["location_name"],
            },
            {"$set": payload, "$inc": {"report_count": 1}},
            upsert=True,
        )
        return
    if json_store is None:
        return
    data = json_store.load()
    roads = data["roads"]
    match = None
    for road in roads:
        if (
            road.get("latitude") == payload["latitude"]
            and road.get("longitude") == payload["longitude"]
            and road.get("location_name") == payload["location_name"]
        ):
            match = road
            break
    if match:
        match.update(payload)
        match["report_count"] = int(match.get("report_count") or 0) + 1
    else:
        payload["report_count"] = 1
        roads.append(payload)
    json_store.save(data)
