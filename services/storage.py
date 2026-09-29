"""Filesystem image storage. MongoDB stores paths, not raw image blobs."""

from __future__ import annotations

import uuid
from pathlib import Path

import cv2
import numpy as np
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "bmp", "webp"}
ALLOWED_VIDEO_EXT = {"mp4", "avi", "mov", "mkv", "webm", "mpeg", "mpg", "wmv", "flv", "3gp", "m4v"}

IMAGE_REQUIRED_MESSAGE = "Please upload an image of the road damage before submitting the report."
VIDEO_NOT_SUPPORTED_MESSAGE = "Please upload an image of the road damage. Video uploads are not supported."


def file_extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def is_video_filename(filename: str | None) -> bool:
    return file_extension(filename) in ALLOWED_VIDEO_EXT


def is_image_filename(filename: str | None) -> bool:
    return file_extension(filename) in ALLOWED_IMAGE_EXT


def looks_like_video_bytes(data: bytes) -> bool:
    if not data or len(data) < 12:
        return False
    if data[4:8] == b"ftyp":
        return True
    if data.startswith(b"RIFF") and b"AVI" in data[:16]:
        return True
    if data.startswith(b"\x1aE\xdf\xa3"):
        return True
    return False


def validate_report_image(data: bytes | None, filename: str | None = "") -> str | None:
    """Return an error message if the upload is not a usable road-damage image."""
    if not data:
        return IMAGE_REQUIRED_MESSAGE
    if is_video_filename(filename) or looks_like_video_bytes(data):
        return VIDEO_NOT_SUPPORTED_MESSAGE
    ext = file_extension(filename)
    if ext and ext not in ALLOWED_IMAGE_EXT:
        return VIDEO_NOT_SUPPORTED_MESSAGE if ext in ALLOWED_VIDEO_EXT else IMAGE_REQUIRED_MESSAGE
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        return VIDEO_NOT_SUPPORTED_MESSAGE if looks_like_video_bytes(data) else IMAGE_REQUIRED_MESSAGE
    return None


class ImageStorage:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.uploads = self.root / "uploads"
        self.results = self.root / "results"
        self.videos = self.root / "videos"
        for folder in (self.uploads, self.results, self.videos):
            folder.mkdir(parents=True, exist_ok=True)

    def _unique_name(self, original: str, folder: Path) -> str:
        ext = Path(original).suffix.lower() or ".jpg"
        name = f"{uuid.uuid4().hex}{ext}"
        return str(folder / name)

    def save_upload(self, file: FileStorage) -> str:
        filename = secure_filename(file.filename or "upload.jpg")
        path = self._unique_name(filename, self.uploads)
        file.save(path)
        return path

    def save_bytes(self, data: bytes, suffix: str = ".jpg") -> str:
        path = self.uploads / f"{uuid.uuid4().hex}{suffix}"
        path.write_bytes(data)
        return str(path)

    def save_result_image(self, frame: np.ndarray) -> str:
        path = self.results / f"{uuid.uuid4().hex}.jpg"
        cv2.imwrite(str(path), frame)
        return str(path)

    def save_video(self, file: FileStorage) -> str:
        filename = secure_filename(file.filename or "video.mp4")
        path = self._unique_name(filename, self.videos)
        file.save(path)
        return path

    def public_relpath(self, abs_path: str | None) -> str | None:
        if not abs_path:
            return None
        path = Path(abs_path)
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return path.name
