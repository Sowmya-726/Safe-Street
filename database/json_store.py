"""JSON file fallback so the app stays runnable without MongoDB."""

from __future__ import annotations

import json
import threading
from pathlib import Path

_lock = threading.Lock()


class JsonStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"users": [], "reports": [], "roads": [], "pending": {}})

    def _read(self) -> dict:
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, data: dict) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, default=str)

    def load(self) -> dict:
        with _lock:
            data = self._read()
            data.setdefault("users", [])
            data.setdefault("reports", [])
            data.setdefault("roads", [])
            data.setdefault("pending", {})
            return data

    def save(self, data: dict) -> None:
        with _lock:
            self._write(data)
