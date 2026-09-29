"""Community analytics derived only from stored reports. Never fabricates values."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

ACTIVE_STATUSES = {"pending", "submitted", "under_review", "verified"}
DUPLICATE_RADIUS_M = 80.0
HOTSPOT_CELL = 0.008
MIN_HEALTH_REPORTS = 3
MIN_TREND_MONTHS = 2
MIN_IMPROVED_AREAS = 1


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def format_distance(meters: float) -> str:
    if meters < 1000:
        return f"{int(round(meters))} m"
    return f"{meters / 1000:.1f} km"


def coords(row: dict) -> tuple[float, float] | None:
    try:
        lat = float(row.get("latitude"))
        lon = float(row.get("longitude"))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def area_key(row: dict) -> str:
    name = (row.get("location_name") or "").strip()
    if name:
        return name
    point = coords(row)
    if point:
        return f"{point[0]:.3f}, {point[1]:.3f}"
    return "Unspecified area"


def same_damage(a: str | None, b: str | None) -> bool:
    left = (a or "").strip().lower()
    right = (b or "").strip().lower()
    if not left or not right:
        return True
    if left in {"undetected", "unknown"} or right in {"undetected", "unknown"}:
        return True
    return left == right


def verification_summary(row: dict) -> dict:
    data = row.get("verification_summary") or {}
    still = int(data.get("still_present") or 0)
    fixed = int(data.get("fixed") or 0)
    unsure = int(data.get("not_sure") or 0)
    if not still and not fixed and not unsure:
        votes = row.get("verification_votes") or []
        for vote in votes:
            choice = (vote.get("vote") or "").lower()
            if choice in {"still_present", "yes"}:
                still += 1
            elif choice in {"fixed", "no"}:
                fixed += 1
            else:
                unsure += 1
    return {"still_present": still, "fixed": fixed, "not_sure": unsure, "total": still + fixed + unsure}


def is_active(row: dict) -> bool:
    return (row.get("status") or "pending") in ACTIVE_STATUSES


def severity_weight(row: dict) -> float:
    key = str(row.get("severity") or "").lower()
    return {"high": 3.0, "medium": 2.0, "low": 1.0}.get(key, 1.2)


def recency_weight(row: dict, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    created = parse_dt(row.get("created_at"))
    if not created:
        return 0.6
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    days = max(0, (now - created).days)
    if days <= 14:
        return 1.4
    if days <= 45:
        return 1.0
    if days <= 90:
        return 0.7
    return 0.4


def health_index(rows: list[dict]) -> dict[str, Any]:
    """Safe Street Road Health Index from real reports only."""
    if len(rows) < MIN_HEALTH_REPORTS:
        return {
            "score": None,
            "label": "Insufficient data",
            "condition": "Insufficient data",
            "enough": False,
            "disclaimer": "Community-based road condition indicator. Not an official government rating.",
            "inputs": {"reports": len(rows)},
        }
    total = len(rows)
    active = sum(1 for r in rows if (r.get("status") or "pending") in {"pending", "submitted", "under_review"})
    high = sum(1 for r in rows if str(r.get("severity") or "").lower() == "high")
    still = sum(verification_summary(r)["still_present"] for r in rows)
    fixed = sum(verification_summary(r)["fixed"] for r in rows)
    votes = sum(verification_summary(r)["total"] for r in rows)
    groups = {r.get("issue_group_id") for r in rows if r.get("issue_group_id")}
    repeated = max(0, total - (len(groups) or total))
    score = 100.0
    score -= 32 * (active / total)
    score -= 18 * (high / total)
    if votes:
        score -= 12 * (still / votes)
        score += 8 * (fixed / votes)
    score -= min(12, repeated * 1.5)
    score = max(0, min(100, round(score)))
    if score >= 80:
        condition = "Good"
    elif score >= 60:
        condition = "Fair"
    elif score >= 40:
        condition = "Poor"
    else:
        condition = "Critical"
    return {
        "score": int(score),
        "label": f"{int(score)} / 100",
        "condition": condition,
        "enough": True,
        "disclaimer": "Safe Street Road Health Index is a community-based road condition indicator, not an official government rating.",
        "inputs": {
            "reports": total,
            "active": active,
            "high_priority": high,
            "community_still_present": still,
        },
    }


def health_by_area(rows: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        buckets.setdefault(area_key(row), []).append(row)
    out = []
    for name, group in buckets.items():
        item = health_index(group)
        item["area"] = name
        item["reports"] = len(group)
        out.append(item)
    out.sort(key=lambda x: (x["score"] is None, x["score"] if x["score"] is not None else 999, x["area"]))
    return out


def find_similar_reports(new_row: dict, existing: list[dict], radius_m: float = DUPLICATE_RADIUS_M) -> list[dict]:
    point = coords(new_row)
    if not point:
        return []
    matches = []
    for row in existing:
        other = coords(row)
        if not other:
            continue
        if new_row.get("public_id") and row.get("public_id") == new_row.get("public_id"):
            continue
        if not same_damage(new_row.get("damage_type"), row.get("damage_type")):
            continue
        dist = haversine_m(point[0], point[1], other[0], other[1])
        if dist <= radius_m:
            item = dict(row)
            item["distance_m"] = round(dist)
            item["distance_label"] = format_distance(dist)
            matches.append(item)
    matches.sort(key=lambda r: r.get("distance_m") or 0)
    return matches


def hotspots(rows: list[dict], min_reports: int = 2) -> list[dict]:
    cells: dict[tuple[float, float], list[dict]] = {}
    for row in rows:
        point = coords(row)
        if not point:
            continue
        key = (round(point[0] / HOTSPOT_CELL) * HOTSPOT_CELL, round(point[1] / HOTSPOT_CELL) * HOTSPOT_CELL)
        cells.setdefault(key, []).append(row)
    out = []
    for (lat, lon), group in cells.items():
        if len(group) < min_reports:
            continue
        points = [coords(r) for r in group if coords(r)]
        if not points:
            continue
        lat = sum(p[0] for p in points) / len(points)
        lon = sum(p[1] for p in points) / len(points)
        active = sum(1 for r in group if is_active(r))
        score = 0.0
        for row in group:
            score += severity_weight(row) * recency_weight(row) * (1.35 if is_active(row) else 0.55)
        names = [area_key(r) for r in group]
        place = max(set(names), key=names.count)
        out.append(
            {
                "latitude": lat,
                "longitude": lon,
                "count": len(group),
                "active": active,
                "score": round(score, 2),
                "area": place,
                "high": sum(1 for r in group if str(r.get("severity") or "").lower() == "high"),
            }
        )
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def monthly_timeline(rows: list[dict]) -> dict[str, Any]:
    if not rows:
        return {"enough": False, "points": [], "disclaimer": "Not enough data available yet."}
    by_month: dict[str, list[dict]] = {}
    for row in rows:
        created = parse_dt(row.get("created_at"))
        if not created:
            continue
        key = created.strftime("%Y-%m")
        by_month.setdefault(key, []).append(row)
    if len(by_month) < MIN_TREND_MONTHS and len(rows) < MIN_HEALTH_REPORTS:
        return {"enough": False, "points": [], "disclaimer": "Not enough data available yet."}
    points = []
    cumulative: list[dict] = []
    for key in sorted(by_month):
        cumulative.extend(by_month[key])
        health = health_index(cumulative)
        still = sum(verification_summary(r)["still_present"] for r in by_month[key])
        active = sum(1 for r in by_month[key] if is_active(r))
        points.append(
            {
                "month": key,
                "label": datetime.strptime(key, "%Y-%m").strftime("%B %Y"),
                "new_reports": len(by_month[key]),
                "active": active,
                "community_still_present": still,
                "condition": health["condition"] if health["enough"] else "Insufficient data",
                "score": health["score"],
            }
        )
    return {
        "enough": True,
        "points": points,
        "disclaimer": "Road Condition Timeline is based on community reports. It is not a scientifically validated road-failure forecast.",
    }


def nearby_reports(lat: float, lon: float, rows: list[dict], radius_m: float = 2500) -> list[dict]:
    out = []
    for row in rows:
        point = coords(row)
        if not point:
            continue
        dist = haversine_m(lat, lon, point[0], point[1])
        if dist <= radius_m:
            item = dict(row)
            item["distance_m"] = round(dist)
            item["distance_label"] = format_distance(dist)
            out.append(item)
    out.sort(key=lambda r: r.get("distance_m") or 0)
    return out


def hazard_assessment(row: dict, group_rows: list[dict] | None = None) -> dict[str, Any]:
    reasons = []
    group = group_rows or [row]
    status = row.get("status") or "pending"
    high = str(row.get("severity") or "").lower() == "high"
    if high:
        reasons.append("This report is marked high priority.")
    if len(group) >= 3:
        reasons.append(f"{len(group)} related reports are grouped at this location.")
    summary = verification_summary(row)
    if summary["still_present"] >= 3 and summary["still_present"] > summary["fixed"]:
        reasons.append("Multiple community members confirmed the damage is still present.")
    created = parse_dt(row.get("created_at"))
    if high and created and status in {"pending", "submitted"}:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - created).days
        if age >= 14:
            reasons.append(f"A high-priority report has remained unreviewed for {age} days.")
    return {
        "is_hazard": bool(reasons),
        "title": "High-Priority Road Hazard" if reasons else "",
        "message": "Multiple reports indicate a potentially hazardous road condition." if len(reasons) > 1 else (reasons[0] if reasons else ""),
        "reasons": reasons,
    }


def attach_hazards(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        gid = row.get("issue_group_id") or row.get("public_id")
        groups.setdefault(gid, []).append(row)
    out = []
    for row in rows:
        gid = row.get("issue_group_id") or row.get("public_id")
        hazard = hazard_assessment(row, groups.get(gid, [row]))
        item = dict(row)
        item["hazard"] = hazard
        out.append(item)
    return out


def most_improved_areas(rows: list[dict]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    recent_cut = now - timedelta(days=60)
    older_cut = now - timedelta(days=120)
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        buckets.setdefault(area_key(row), []).append(row)
    improved = []
    for name, group in buckets.items():
        older = []
        recent = []
        for row in group:
            created = parse_dt(row.get("created_at"))
            if not created:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if older_cut <= created < recent_cut:
                older.append(row)
            elif created >= recent_cut:
                recent.append(row)
        if len(older) < MIN_HEALTH_REPORTS or len(recent) < MIN_HEALTH_REPORTS:
            continue
        before = health_index(older)
        after = health_index(recent)
        if not before["enough"] or not after["enough"]:
            continue
        if after["score"] is None or before["score"] is None:
            continue
        if after["score"] <= before["score"]:
            continue
        improved.append(
            {
                "area": name,
                "from": before["score"],
                "to": after["score"],
                "delta": after["score"] - before["score"],
            }
        )
    improved.sort(key=lambda x: x["delta"], reverse=True)
    return {
        "enough": bool(improved),
        "areas": improved[:12],
        "disclaimer": "Most improved areas are based on Safe Street community reports, not an official ranking.",
    }


def area_metrics(rows: list[dict]) -> dict[str, Any]:
    health = health_index(rows)
    votes = sum(verification_summary(r)["total"] for r in rows)
    return {
        "reports": len(rows),
        "active": sum(1 for r in rows if is_active(r)),
        "verified": sum(1 for r in rows if (r.get("status") or "") == "verified"),
        "high": sum(1 for r in rows if str(r.get("severity") or "").lower() == "high"),
        "recent": sum(1 for r in rows if (str(r.get("created_at") or "")[:10] >= (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat())),
        "health": health,
        "verification": votes,
        "hotspots": len(hotspots(rows, min_reports=2)),
    }


def compare_areas(rows: list[dict], area_a: str, area_b: str) -> dict[str, Any]:
    a = [r for r in rows if area_a.lower() in area_key(r).lower()]
    b = [r for r in rows if area_b.lower() in area_key(r).lower()]
    return {
        "area_a": area_a,
        "area_b": area_b,
        "left": area_metrics(a),
        "right": area_metrics(b),
        "enough": bool(a or b),
    }


def apply_filters(rows: list[dict], args) -> tuple[list[dict], dict, list[str]]:
    severity = (args.get("severity") or "").strip()
    damage = (args.get("damage_type") or "").strip()
    status = (args.get("status") or "").strip()
    date = (args.get("date") or "").strip()
    date_from = (args.get("date_from") or "").strip()
    date_to = (args.get("date_to") or "").strip()
    query = (args.get("q") or "").strip()
    location = (args.get("location") or args.get("area") or "").strip()
    resolved = (args.get("resolved") or "").strip()
    group = (args.get("issue_group") or args.get("group") or "").strip()
    verification = (args.get("verification") or "").strip()
    hotspot_only = (args.get("hotspot") or "").strip() in {"1", "on", "true", "yes"}
    nearby_km = (args.get("nearby") or "").strip()
    lat = args.get("lat")
    lon = args.get("lng") or args.get("lon")

    filtered = list(rows)
    if severity:
        filtered = [r for r in filtered if str(r.get("severity") or "").lower() == severity.lower()]
    if damage:
        filtered = [r for r in filtered if (r.get("damage_type") or "") == damage]
    if status:
        filtered = [r for r in filtered if (r.get("status") or "pending") == status]
    if resolved == "yes":
        filtered = [r for r in filtered if (r.get("status") or "") == "verified"]
    elif resolved == "no":
        filtered = [r for r in filtered if (r.get("status") or "pending") != "verified"]
    if date:
        filtered = [r for r in filtered if str(r.get("created_at") or "").startswith(date)]
    if date_from:
        filtered = [r for r in filtered if str(r.get("created_at") or "")[:10] >= date_from]
    if date_to:
        filtered = [r for r in filtered if str(r.get("created_at") or "")[:10] <= date_to]
    if query:
        needle = query.lower()
        filtered = [
            r
            for r in filtered
            if needle in str(r.get("location_name") or "").lower()
            or needle in str(r.get("damage_type") or "").lower()
            or needle in str(r.get("description") or "").lower()
            or needle in str(r.get("public_id") or "").lower()
            or needle in str(r.get("issue_group_id") or "").lower()
        ]
    if location:
        needle = location.lower()
        filtered = [r for r in filtered if needle in str(r.get("location_name") or "").lower()]
    if group:
        filtered = [r for r in filtered if str(r.get("issue_group_id") or "") == group]
    if verification == "confirmed":
        filtered = [r for r in filtered if verification_summary(r)["still_present"] > 0]
    elif verification == "fixed":
        filtered = [r for r in filtered if verification_summary(r)["fixed"] > 0]
    if hotspot_only:
        cells = {(round(h["latitude"], 5), round(h["longitude"], 5)) for h in hotspots(rows)}
        keep = []
        for row in filtered:
            point = coords(row)
            if not point:
                continue
            key = (round(round(point[0] / HOTSPOT_CELL) * HOTSPOT_CELL, 5), round(round(point[1] / HOTSPOT_CELL) * HOTSPOT_CELL, 5))
            if key in cells:
                keep.append(row)
        filtered = keep
    if nearby_km:
        try:
            radius = float(nearby_km) * 1000
            user_lat = float(lat)
            user_lon = float(lon)
            nearby = nearby_reports(user_lat, user_lon, filtered, radius_m=radius)
            filtered = nearby
        except (TypeError, ValueError):
            pass

    types = sorted({r.get("damage_type") for r in rows if r.get("damage_type")})
    filters = {
        "severity": severity,
        "damage_type": damage,
        "status": status,
        "date": date,
        "date_from": date_from,
        "date_to": date_to,
        "q": query,
        "location": location,
        "resolved": resolved,
        "issue_group": group,
        "verification": verification,
        "hotspot": "1" if hotspot_only else "",
        "nearby": nearby_km,
        "lat": lat or "",
        "lng": lon or "",
    }
    return filtered, filters, types


def paginate(rows: list[dict], page: int, per_page: int = 20) -> dict[str, Any]:
    page = max(1, page)
    total = len(rows)
    pages = max(1, math.ceil(total / per_page)) if total else 1
    page = min(page, pages)
    start = (page - 1) * per_page
    return {
        "items": rows[start : start + per_page],
        "page": page,
        "pages": pages,
        "total": total,
        "per_page": per_page,
        "has_prev": page > 1,
        "has_next": page < pages,
    }
