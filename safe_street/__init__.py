from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from safe_street.config import Config


def create_app() -> Flask:
    load_dotenv()
    os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(".ultralytics").resolve()))

    root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )
    app.config.from_object(Config)

    Config.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    Config.DATA_ROOT.mkdir(parents=True, exist_ok=True)

    from database.indexes import ensure_indexes
    from database.json_store import JsonStore
    from database.users import ensure_initial_admin
    from safe_street.routes import register_routes

    ensure_indexes()
    ensure_initial_admin(JsonStore(Config.DATA_ROOT / "local_store.json"))
    register_routes(app)
    return app
