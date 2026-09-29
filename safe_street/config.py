import os
from datetime import timedelta
from pathlib import Path


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    MAX_CONTENT_LENGTH = 120 * 1024 * 1024
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "media")).resolve()
    DATA_ROOT = Path(os.getenv("DATA_ROOT", "data")).resolve()
    ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "bmp", "webp"}
    ALLOWED_VIDEO_EXT = {"mp4", "avi", "mov", "mkv"}
