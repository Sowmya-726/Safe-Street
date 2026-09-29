"""
Severity display helpers.

There is no separate trained severity model in this project.
M1 already includes a 'Crack-Severe' class. Other values are a
transparent heuristic from existing YOLO labels + confidence so the
UI can show Low / Medium / High. Marked as heuristic, not ML.
"""

from __future__ import annotations

# Placeholder map — not a trained classifier.
_LABEL_BASE = {
    "crack-severe": "high",
    "pothole": "high",
    "crack": "medium",
    "speed-bump": "low",
    "speedbump": "low",
}


def infer_severity(detection_summary: list[dict]) -> dict:
    """
    Return a UI severity payload.

    source:
      - 'heuristic_from_yolo_labels' when detections exist
      - 'placeholder' when nothing was detected
    """
    if not detection_summary:
        return {
            "level": None,
            "label": "Not assessed",
            "source": "placeholder",
            "note": "Severity is a placeholder until detections exist. This is not a separate ML model.",
        }

    rank = {"low": 1, "medium": 2, "high": 3}
    best_level = "low"
    for item in detection_summary:
        key = str(item.get("label", "")).strip().lower().replace(" ", "-")
        level = _LABEL_BASE.get(key, "medium")
        conf = float(item.get("confidence") or 0)
        if level == "medium" and conf >= 0.85:
            level = "high"
        if level == "low" and conf >= 0.9:
            level = "medium"
        if rank[level] > rank[best_level]:
            best_level = level

    return {
        "level": best_level,
        "label": best_level.capitalize(),
        "source": "heuristic_from_yolo_labels",
        "note": "Derived from existing YOLO class names (e.g. Crack-Severe) and confidence. Not a dedicated severity network.",
    }
