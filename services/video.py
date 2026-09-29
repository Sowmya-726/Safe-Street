"""Video processing uses the same process_frame loop as the Streamlit app."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import cv2

from services.inference import process_frame

logger = logging.getLogger(__name__)


def process_video_file(
    input_path: str,
    models: dict,
    thresholds: dict,
    output_dir: Path,
) -> tuple[str | None, str | None]:
    cap = None
    writer = None
    output_path = None
    try:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return None, "Error opening uploaded video file."

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"processed_{Path(input_path).stem}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            return None, "Error initializing video writer."

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(process_frame(frame, models, thresholds))

        return output_path, None
    except Exception as exc:
        logger.error("Video processing failed", exc_info=exc)
        return None, str(exc)
    finally:
        if cap is not None:
            cap.release()
        if writer is not None:
            writer.release()
