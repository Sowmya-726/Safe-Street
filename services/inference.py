"""
Existing YOLOv8 inference — extracted from main.py without changing model
weights, architecture, class filters, or prediction settings.

Do not retrain or replace models from this module.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import cv2
import numpy as np
import supervision as sv
from ultralytics import YOLO

os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(".ultralytics").resolve()))

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATHS = {
    "M1 (Model 1)": str(PROJECT_ROOT / "models" / "m1-best.pt"),
    "M2 (Model 2)": str(PROJECT_ROOT / "models" / "m2-road-damage.pt"),
}
MODEL_PREFIX = {
    "M1 (Model 1)": "M1",
    "M2 (Model 2)": "M2",
}
DEFAULT_CONF = {"M1 (Model 1)": 0.35, "M2 (Model 2)": 0.40}
FALLBACK_CONF = {"M1 (Model 1)": 0.15, "M2 (Model 2)": 0.18}
DEFECT_CLASS_IDS = {
    "M1 (Model 1)": [3, 4, 5, 6],
    "M2 (Model 2)": [0, 1, 2, 3],
}
PREDICT_IMGSZ = 1280
LIVE_FEED_TARGET_WIDTH = 640

_LOADED_MODELS: dict[str, tuple] = {}


def load_yolo_model(path: str):
    try:
        model = YOLO(path)
        logger.info("Successfully loaded model from %s", path)
        return model, model.names
    except Exception as e:
        logger.error("Failed to load model at %s", path, exc_info=e)
        return None, {}


def make_annotators(color: sv.Color):
    box_annotator = sv.BoxAnnotator(thickness=1, color=color)
    label_annotator = sv.LabelAnnotator(
        text_thickness=1,
        text_scale=0.4,
        color=sv.Color.WHITE,
        text_color=sv.Color.BLACK,
        text_padding=2,
    )
    return box_annotator, label_annotator


def run_model_prediction(
    model_name: str,
    model,
    frame: np.ndarray,
    conf_threshold: float,
    defect_only: bool,
):
    predict_kwargs = {
        "source": frame,
        "conf": conf_threshold,
        "verbose": False,
        "imgsz": PREDICT_IMGSZ,
    }
    if defect_only:
        predict_kwargs["classes"] = DEFECT_CLASS_IDS[model_name]
    return model.predict(**predict_kwargs)[0]


def analyze_frame(
    frame: np.ndarray, models: dict[str, tuple], thresholds: dict[str, float]
):
    annotated_frame = frame.copy()
    detection_summary = []
    found_defects = False

    for model_name, (model, names_map, box_ann, label_ann) in models.items():
        try:
            results = run_model_prediction(
                model_name, model, frame, thresholds[model_name], defect_only=True
            )
            detections = sv.Detections.from_ultralytics(results)

            if len(detections) == 0:
                results = run_model_prediction(
                    model_name,
                    model,
                    frame,
                    FALLBACK_CONF[model_name],
                    defect_only=True,
                )
                detections = sv.Detections.from_ultralytics(results)

            labels = [
                f"{MODEL_PREFIX[model_name]}:{names_map.get(cls_id, str(cls_id))} {conf:.2f}"
                for cls_id, conf in zip(detections.class_id, detections.confidence)
            ]

            annotated_frame = box_ann.annotate(annotated_frame, detections)
            annotated_frame = label_ann.annotate(
                annotated_frame, detections, labels=labels
            )

            for cls_id, conf in zip(detections.class_id, detections.confidence):
                label = names_map.get(int(cls_id), str(int(cls_id)))
                detection_summary.append(
                    {
                        "model": model_name,
                        "label": label,
                        "confidence": round(float(conf), 3),
                    }
                )
            if len(detections) > 0:
                found_defects = True
        except Exception as e:
            logger.error("Error during prediction/annotation for %s: %s", model_name, e)
            cv2.putText(
                annotated_frame,
                f"Error processing {model_name}",
                (10, 30 + list(models.keys()).index(model_name) * 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )

    detection_summary.sort(key=lambda item: item["confidence"], reverse=True)
    return annotated_frame, detection_summary, found_defects


def process_frame(
    frame: np.ndarray, models: dict[str, tuple], thresholds: dict[str, float]
) -> np.ndarray:
    annotated_frame, _, _ = analyze_frame(frame, models, thresholds)
    return annotated_frame


def load_default_models() -> tuple[dict[str, tuple], dict[str, float], list[str]]:
    """Load both packaged models once (used by the Flask app)."""
    global _LOADED_MODELS
    errors: list[str] = []
    if _LOADED_MODELS:
        thresholds = {name: DEFAULT_CONF[name] for name in _LOADED_MODELS}
        return _LOADED_MODELS, thresholds, errors

    loaded: dict[str, tuple] = {}
    for name, path in MODEL_PATHS.items():
        if not Path(path).is_file():
            errors.append(f"Model file not found: {path}")
            continue
        model, names_map = load_yolo_model(path)
        if model and names_map:
            color = (
                sv.Color.WHITE
                if name == "M1 (Model 1)"
                else sv.Color.from_hex("#9c9c9c")
            )
            box_ann, label_ann = make_annotators(color)
            loaded[name] = (model, names_map, box_ann, label_ann)
        else:
            errors.append(f"Failed to load model: {path}")

    _LOADED_MODELS = loaded
    thresholds = {name: DEFAULT_CONF[name] for name in loaded}
    return loaded, thresholds, errors


def summarize_detections(detection_summary: list[dict]) -> dict:
    if not detection_summary:
        return {
            "total_detections": 0,
            "highest_confidence": 0.0,
            "damage_types": [],
            "primary_damage_type": None,
            "primary_confidence": 0.0,
            "detections": [],
        }
    types = []
    seen = set()
    for item in detection_summary:
        label = item["label"]
        if label not in seen:
            types.append(label)
            seen.add(label)
    strongest = detection_summary[0]
    return {
        "total_detections": len(detection_summary),
        "highest_confidence": strongest["confidence"],
        "damage_types": types,
        "primary_damage_type": strongest["label"],
        "primary_confidence": strongest["confidence"],
        "detections": detection_summary,
    }


def decode_image_bytes(data: bytes):
    file_bytes = np.asarray(bytearray(data), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    return img


def encode_jpeg(frame: np.ndarray) -> bytes:
    success, encoded = cv2.imencode(".jpg", frame)
    if not success:
        raise ValueError("Could not encode annotated image")
    return encoded.tobytes()
