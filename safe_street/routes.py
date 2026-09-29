from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from database.reports import (
    ReportRepository,
    public_report,
    severity_label,
    status_label,
)
from database.json_store import JsonStore
from database.pending import PendingDetectionStore
from database.roads import upsert_road_from_report
from database.users import UserRepository, is_admin_user, public_user
from safe_street.auth import hash_password, validate_registration, verify_password
from safe_street.extra_routes import register_extended_routes
from services.civic import apply_filters, attach_hazards, find_similar_reports, hotspots
from services.inference import (
    analyze_frame,
    decode_image_bytes,
    encode_jpeg,
    load_default_models,
    summarize_detections,
)
from services.severity import infer_severity
from services.storage import ALLOWED_IMAGE_EXT, ALLOWED_VIDEO_EXT, ImageStorage
from services.video import process_video_file


def register_routes(app: Flask) -> None:
    json_store = JsonStore(Path(app.config["DATA_ROOT"]) / "local_store.json")
    users = UserRepository(json_store)
    reports = ReportRepository(json_store)
    pending = PendingDetectionStore(json_store)
    storage = ImageStorage(Path(app.config["MEDIA_ROOT"]))

    def current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None
        found = users.find_by_id(str(user_id))
        if not found:
            return None
        return public_user(found)

    def safe_next(value: str | None, fallback: str) -> str:
        nxt = (value or "").strip()
        if nxt.startswith("/") and not nxt.startswith("//"):
            return nxt
        return fallback

    def start_session(user: dict, *, permanent: bool = False) -> None:
        session.clear()
        session["user_id"] = str(user["id"])
        session["user_name"] = user.get("name") or ""
        session["role"] = "admin" if is_admin_user(user) else "user"
        session.permanent = bool(permanent)

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                if session.get("user_id"):
                    session.clear()
                path = request.full_path.rstrip("?") if request.query_string else request.path
                if path.startswith("/report") or path.startswith("/detect"):
                    flash("Please sign in to submit a report.", "error")
                else:
                    flash("Please sign in to continue.", "error")
                return redirect(url_for("login", next=path))
            return view(*args, **kwargs)

        return wrapped

    def nav_items(user):
        public = [
            {"endpoint": "landing", "label": "Home", "match": ("landing",)},
            {"endpoint": "explore", "label": "Explore", "match": ("explore",)},
            {"endpoint": "damage_map", "label": "Map", "match": ("damage_map",)},
            {"endpoint": "dashboard", "label": "Dashboard", "match": ("dashboard", "analytics")},
            {"endpoint": "insights", "label": "Insights", "match": ("insights", "road_health", "damage_hotspots", "road_trends", "nearby", "compare", "improved_roads")},
        ]
        if user and user.get("is_admin"):
            return public + [
                {"endpoint": "admin_dashboard", "label": "Admin Dashboard", "match": ("admin_dashboard",)},
                {"endpoint": "admin_reports", "label": "Reports", "match": ("admin_reports", "admin_report_detail")},
                {"endpoint": "admin_high_priority", "label": "High Priority", "match": ("admin_high_priority",)},
                {"endpoint": "admin_verification", "label": "Verification", "match": ("admin_verification",)},
                {"endpoint": "admin_analytics", "label": "Analytics", "match": ("admin_analytics",)},
                {"endpoint": "admin_logout", "label": "Logout", "match": ("admin_logout", "logout")},
            ]
        items = public + [
            {"endpoint": "report_damage", "label": "Report Road Damage", "match": ("report_damage", "report_detect", "report_preview", "report_submit")},
        ]
        if user:
            items.extend(
                [
                    {"endpoint": "my_reports", "label": "My Reports", "match": ("my_reports",)},
                    {"endpoint": "profile", "label": "Profile", "match": ("profile", "profile_edit", "profile_password")},
                    {"endpoint": "logout", "label": "Logout", "match": ("logout",)},
                ]
            )
        else:
            items.extend(
                [
                    {"endpoint": "login", "label": "Login", "match": ("login", "login_post")},
                    {"endpoint": "register", "label": "Register", "match": ("register", "register_post")},
                    {"endpoint": "admin_login", "label": "Admin Login", "match": ("admin_login", "admin_login_post")},
                ]
            )
        return items

    @app.context_processor
    def inject_globals():
        user = current_user()
        return {
            "nav_items": nav_items(user),
            "current_user": user,
            "status_label": status_label,
            "severity_label": severity_label,
        }

    def allowed(filename: str, allowed_ext: set[str]) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_ext

    def draft_from_result(result: dict, extra: dict | None = None) -> dict:
        payload = {
            "original_rel": result["original_rel"],
            "result_rel": result["result_rel"],
            "damage_type": result["summary"]["primary_damage_type"],
            "confidence": result["summary"]["primary_confidence"],
            "severity": result["severity"]["level"],
            "severity_note": result["severity"]["note"],
            "detections": result["summary"]["detections"],
            "original_path": result["original_path"],
            "result_path": result["result_path"],
        }
        if extra:
            payload.update(extra)
        return payload

    def save_draft(user_id: str, payload: dict) -> dict:
        pending.set(user_id, payload)
        return payload

    def run_image_detection(image_bytes: bytes) -> dict:
        models, thresholds, errors = load_default_models()
        if not models:
            raise RuntimeError("analysis_unavailable")
        img = decode_image_bytes(image_bytes)
        if img is None:
            raise ValueError("Could not read that photo. Please upload a JPG, PNG, BMP, or WebP image.")
        annotated, detection_summary, found = analyze_frame(img, models, thresholds)
        summary = summarize_detections(detection_summary)
        severity = infer_severity(detection_summary)
        original_path = storage.save_bytes(image_bytes, ".jpg")
        result_path = storage.save_result_image(annotated)
        return {
            "original_path": original_path,
            "result_path": result_path,
            "original_rel": storage.public_relpath(original_path),
            "result_rel": storage.public_relpath(result_path),
            "found_defects": found,
            "summary": summary,
            "severity": severity,
            "model_warnings": errors,
        }

    def filter_report_rows(rows: list[dict]) -> tuple[list[dict], dict, list[str]]:
        return apply_filters(rows, request.args)

    def friendly_detect_error(exc: Exception) -> str:
        if isinstance(exc, RuntimeError):
            return "We could not analyze the road image right now. Please try again in a moment."
        return str(exc)

    @app.get("/")
    def landing():
        stats = reports.stats_all()
        recent = [public_report(r) for r in reports.list_all()[:3]]
        return render_template("landing.html", stats=stats, recent=recent)

    @app.get("/register")
    def register():
        user = current_user()
        if user:
            if user.get("is_admin"):
                return redirect(url_for("admin_dashboard"))
            return redirect(safe_next(request.args.get("next"), url_for("landing")))
        return render_template("auth/register.html", next=request.args.get("next", ""))

    @app.post("/register")
    def register_post():
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        nxt = request.form.get("next") or request.args.get("next")
        errors = validate_registration(name, email, password, confirm)
        if users.find_by_email(email):
            errors.append("An account with this email already exists.")
        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("auth/register.html", name=name, email=email, next=nxt or "")
        created = users.create(name, email, hash_password(password), role="user")
        start_session(created)
        flash("Account created. Welcome to Safe Street.", "success")
        return redirect(safe_next(nxt, url_for("report_damage")))

    @app.get("/login")
    def login():
        user = current_user()
        if user:
            if user.get("is_admin"):
                return redirect(url_for("admin_dashboard"))
            return redirect(safe_next(request.args.get("next"), url_for("landing")))
        return render_template("auth/login.html", next=request.args.get("next", ""), email="")

    @app.post("/login")
    def login_post():
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"
        nxt = request.form.get("next") or request.args.get("next")
        user = users.find_by_email(email)
        if not user or not verify_password(user.get("password_hash", ""), password):
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", email=email, next=nxt or "")
        if is_admin_user(user):
            flash("Administrator accounts must use the administrator sign-in.", "error")
            return redirect(url_for("admin_login", next=nxt or ""))
        start_session(user, permanent=bool(remember))
        flash(f"Welcome back, {user['name']}.", "success")
        return redirect(safe_next(nxt, url_for("dashboard")))

    @app.get("/forgot-password")
    def forgot_password():
        return render_template("auth/forgot.html")

    @app.post("/forgot-password")
    def forgot_password_post():
        flash(
            "Password reset by email is not available here. Sign in and use Profile to change your password.",
            "info",
        )
        return render_template("auth/forgot.html")

    @app.get("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("landing"))

    @app.get("/dashboard")
    def dashboard():
        rows = reports.list_all()
        stats = reports.stats_all()
        filtered, filters, types = filter_report_rows(rows)
        recent = [public_report(r) for r in filtered[:12]]
        return render_template(
            "dashboard.html",
            stats=stats,
            recent=recent,
            filters=filters,
            types=types,
            total_shown=len(filtered),
        )

    @app.get("/explore")
    def explore():
        rows = reports.list_all()
        filtered, filters, types = filter_report_rows(rows)
        return render_template(
            "explore.html",
            reports=[public_report(r) for r in filtered],
            types=types,
            filters=filters,
            total=len(rows),
        )

    @app.get("/detect")
    @login_required
    def detect():
        mode = request.args.get("mode", "image")
        if mode not in {"image", "video", "live"}:
            mode = "image"
        if mode == "live":
            return redirect(url_for("detect_live"))
        return render_template("detect.html", result=None, mode=mode)

    @app.post("/detect/image")
    @login_required
    def detect_image():
        file = request.files.get("image")
        if not file or not file.filename:
            flash("Upload a road image first.", "error")
            return redirect(url_for("detect"))
        if not allowed(file.filename, ALLOWED_IMAGE_EXT):
            flash("Please use a JPG, PNG, BMP, or WebP image.", "error")
            return redirect(url_for("detect"))
        try:
            result = run_image_detection(file.read())
        except Exception as exc:
            flash(friendly_detect_error(exc), "error")
            return redirect(url_for("detect"))
        save_draft(str(session["user_id"]), draft_from_result(result))
        return render_template("detect.html", result=result, mode="image")

    @app.post("/detect/video")
    @login_required
    def detect_video():
        file = request.files.get("video")
        if not file or not file.filename:
            flash("Upload a video first.", "error")
            return render_template("detect.html", result=None, mode="video")
        if not allowed(file.filename, ALLOWED_VIDEO_EXT):
            flash("Please use an MP4, AVI, MOV, or MKV video.", "error")
            return render_template("detect.html", result=None, mode="video")
        models, thresholds, errors = load_default_models()
        if not models:
            flash("Video analysis is unavailable right now. Please try again later.", "error")
            return render_template("detect.html", result=None, mode="video")
        input_path = storage.save_video(file)
        output_path, error = process_video_file(
            input_path, models, thresholds, Path(app.config["MEDIA_ROOT"]) / "videos"
        )
        if error:
            flash("Could not process that video. Please try another clip.", "error")
            return render_template("detect.html", result=None, mode="video")
        return render_template(
            "detect.html",
            result=None,
            mode="video",
            video_rel=storage.public_relpath(output_path),
            model_warnings=errors,
        )

    @app.get("/detect/live")
    @login_required
    def detect_live():
        return render_template("detect.html", result=None, mode="live")

    @app.post("/api/live-frame")
    @login_required
    def live_frame():
        file = request.files.get("frame")
        if not file:
            return jsonify({"error": "No frame received"}), 400
        models, thresholds, errors = load_default_models()
        if not models:
            return jsonify({"error": "Analysis is unavailable right now"}), 500
        img = decode_image_bytes(file.read())
        if img is None:
            return jsonify({"error": "Could not read this camera frame"}), 400
        annotated, summary, found = analyze_frame(img, models, thresholds)
        jpeg = encode_jpeg(annotated)
        return Response(jpeg, mimetype="image/jpeg")

    @app.get("/report")
    @login_required
    def report_damage():
        preset = pending.get(str(session["user_id"]))
        return render_template("report.html", preset=preset, confirm=False)

    @app.post("/report/detect")
    @login_required
    def report_detect():
        file = request.files.get("image")
        if not file or not file.filename:
            flash("Upload a road image to continue.", "error")
            return redirect(url_for("report_damage"))
        if not allowed(file.filename, ALLOWED_IMAGE_EXT):
            flash("Please use a JPG, PNG, BMP, or WebP image.", "error")
            return redirect(url_for("report_damage"))
        try:
            result = run_image_detection(file.read())
        except Exception as exc:
            flash(friendly_detect_error(exc), "error")
            return redirect(url_for("report_damage"))
        preset = save_draft(
            str(session["user_id"]),
            draft_from_result(
                result,
                {
                    "location_name": request.form.get("location_name", ""),
                    "latitude": request.form.get("latitude", ""),
                    "longitude": request.form.get("longitude", ""),
                    "description": request.form.get("description", ""),
                },
            ),
        )
        return render_template("report.html", preset=preset, confirm=False)

    @app.post("/report/preview")
    @login_required
    def report_preview():
        preset = pending.get(str(session["user_id"]))
        location_name = request.form.get("location_name", "").strip()
        latitude = request.form.get("latitude", "").strip()
        longitude = request.form.get("longitude", "").strip()
        description = request.form.get("description", "").strip()
        if not preset.get("original_path"):
            flash("Analyze a road photo before submitting a report.", "error")
            return redirect(url_for("report_damage"))
        if not location_name and not (latitude and longitude):
            flash("Add a location or choose a point on the map before continuing.", "error")
            preset.update(
                {
                    "location_name": location_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "description": description,
                }
            )
            save_draft(str(session["user_id"]), preset)
            return render_template("report.html", preset=preset, confirm=False)
        lat_val = lon_val = None
        try:
            if latitude:
                lat_val = float(latitude)
            if longitude:
                lon_val = float(longitude)
        except ValueError:
            flash("The selected location could not be saved. Please choose it again on the map.", "error")
            return render_template("report.html", preset=preset, confirm=False)
        if lat_val is not None and not -90 <= lat_val <= 90:
            flash("Please choose a valid location on the map.", "error")
            return render_template("report.html", preset=preset, confirm=False)
        if lon_val is not None and not -180 <= lon_val <= 180:
            flash("Please choose a valid location on the map.", "error")
            return render_template("report.html", preset=preset, confirm=False)
        preset.update(
            {
                "location_name": location_name,
                "latitude": lat_val,
                "longitude": lon_val,
                "description": description,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        similar = find_similar_reports(
            {
                "damage_type": preset.get("damage_type"),
                "latitude": lat_val,
                "longitude": lon_val,
            },
            reports.list_all(),
        )
        preset["similar"] = [public_report(r) for r in similar]
        save_draft(str(session["user_id"]), preset)
        return render_template("report.html", preset=preset, confirm=True, similar=preset["similar"])

    @app.post("/report/submit")
    @login_required
    def report_submit():
        user = current_user()
        if not user:
            flash("Please sign in to submit a report.", "error")
            return redirect(url_for("login", next=request.path))
        preset = pending.get(str(user["id"]))
        if not preset.get("original_path"):
            flash("Nothing to submit. Analyze a road photo first.", "error")
            return redirect(url_for("report_damage"))
        similar = find_similar_reports(
            {
                "damage_type": preset.get("damage_type"),
                "latitude": preset.get("latitude"),
                "longitude": preset.get("longitude"),
            },
            reports.list_all(),
        )
        join_id = request.form.get("join_group_id") or ""
        group_id = None
        duplicate_of = None
        related = []
        if join_id:
            match = next((r for r in similar if r.get("public_id") == join_id or r.get("issue_group_id") == join_id), None)
            if match:
                group_id = match.get("issue_group_id") or match.get("public_id")
                duplicate_of = match.get("public_id")
                related = [match.get("public_id")]
        created = reports.create(
            {
                "user_id": str(user["id"]),
                "image": preset.get("original_rel"),
                "result_image": preset.get("result_rel"),
                "damage_type": preset.get("damage_type") or "Undetected",
                "severity": preset.get("severity"),
                "confidence": preset.get("confidence") or 0,
                "location_name": preset.get("location_name") or "Unnamed location",
                "latitude": preset.get("latitude"),
                "longitude": preset.get("longitude"),
                "description": preset.get("description") or "",
                "detections": preset.get("detections") or [],
                "issue_group_id": group_id,
                "duplicate_of": duplicate_of,
                "related_report_ids": related,
            }
        )
        upsert_road_from_report(created, json_store)
        pending.clear(str(user["id"]))
        flash("Your report has been submitted successfully.", "success")
        return render_template(
            "report_success.html",
            report=public_report(created),
            grouped=bool(duplicate_of),
        )

    @app.get("/reports")
    @login_required
    def my_reports():
        user = current_user()
        if not user:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        rows = reports.list_for_user(str(user["id"]))
        filtered, filters, types = filter_report_rows(rows)
        return render_template(
            "my_reports.html",
            reports=[public_report(r) for r in filtered],
            types=types,
            filters=filters,
        )

    @app.get("/reports/<report_id>")
    def report_detail(report_id: str):
        row = reports.get_by_id(report_id)
        if not row:
            abort(404)
        user = current_user()
        group = reports.list_group(row.get("issue_group_id") or "")
        hazards = attach_hazards([row] + group)
        report = public_report(hazards[0])
        already = reports.user_has_verified(row, user["id"] if user else None)
        return render_template(
            "report_detail.html",
            report=report,
            related=[public_report(r) for r in group if r.get("public_id") != row.get("public_id")],
            already_verified=already,
            can_verify=bool(user),
        )

    @app.get("/analytics")
    def analytics():
        rows = reports.list_all()
        stats = reports.stats_all()
        return render_template("analytics.html", stats=stats, count=len(rows))

    @app.get("/map")
    def damage_map():
        rows = reports.list_all()
        filtered, filters, types = filter_report_rows(rows)
        mapped = [
            public_report(r)
            for r in attach_hazards(filtered)
            if r.get("latitude") not in (None, "") and r.get("longitude") not in (None, "")
        ]
        spots = hotspots(filtered)
        return render_template(
            "map.html",
            reports=mapped,
            all_count=len(rows),
            filters=filters,
            types=types,
            hotspots=spots,
        )

    @app.get("/profile")
    @login_required
    def profile():
        user = current_user()
        if not user:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        stats = reports.stats_for_user(str(user["id"]))
        return render_template("profile.html", user=user, stats=stats)

    @app.post("/profile/edit")
    @login_required
    def profile_edit():
        user = current_user()
        if not user:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login", next=url_for("profile")))
        name = request.form.get("name", "").strip()
        if len(name) < 2:
            flash("Name must be at least 2 characters.", "error")
            return redirect(url_for("profile"))
        updated = users.update_profile(str(user["id"]), name)
        session["user_name"] = updated["name"] if updated else name
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))

    @app.post("/profile/password")
    @login_required
    def profile_password():
        user = current_user()
        if not user:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login", next=url_for("profile")))
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        fresh = users.find_by_id(str(user["id"]))
        if not fresh or not verify_password(fresh.get("password_hash", ""), current):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("profile"))
        if len(new) < 8:
            flash("New password must be at least 8 characters.", "error")
            return redirect(url_for("profile"))
        if new != confirm:
            flash("New password and confirmation do not match.", "error")
            return redirect(url_for("profile"))
        users.update_password(str(user["id"]), hash_password(new))
        flash("Password changed.", "success")
        return redirect(url_for("profile"))

    @app.get("/admin")
    def admin_root():
        return redirect(url_for("admin_dashboard"))

    @app.get("/media/<path:filename>")
    def media(filename: str):
        return send_from_directory(app.config["MEDIA_ROOT"], filename)

    register_extended_routes(app, users, reports, storage, current_user, login_required, allowed)

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(_e):
        flash("That file is too large to upload.", "error")
        return redirect(request.referrer or url_for("landing"))
