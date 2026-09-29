from __future__ import annotations

from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database.reports import ADMIN_TRANSITIONS, admin_report, public_report, status_label
from database.users import is_admin_user
from services.civic import (
    apply_filters,
    area_key,
    attach_hazards,
    compare_areas,
    health_by_area,
    health_index,
    hotspots,
    most_improved_areas,
    monthly_timeline,
    nearby_reports,
    paginate,
)
from services.storage import ALLOWED_IMAGE_EXT


def register_extended_routes(app: Flask, users, reports, storage, current_user, login_required, allowed) -> None:
    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                if session.get("user_id"):
                    session.clear()
                flash("Administrator sign-in is required.", "error")
                return redirect(url_for("admin_login", next=request.path))
            if not user.get("is_admin"):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    def current_admin():
        user = current_user()
        if not user or not user.get("is_admin"):
            return None
        return user

    @app.get("/insights")
    def insights():
        rows = reports.list_all()
        health = health_index(rows)
        spots = hotspots(rows)
        trend = monthly_timeline(rows)
        improved = most_improved_areas(rows)
        return render_template(
            "insights.html",
            health=health,
            hotspot_count=len(spots),
            trend=trend,
            improved=improved,
            stats=reports.stats_all(),
        )

    @app.get("/health")
    def road_health():
        rows = reports.list_all()
        area = (request.args.get("area") or "").strip()
        scoped = [r for r in rows if area.lower() in area_key(r).lower()] if area else rows
        return render_template(
            "health.html",
            health=health_index(scoped),
            areas=health_by_area(rows),
            area=area,
            count=len(scoped),
        )

    @app.get("/hotspots")
    def damage_hotspots():
        rows = reports.list_all()
        spots = hotspots(rows)
        mapped = [
            public_report(r)
            for r in rows
            if r.get("latitude") not in (None, "") and r.get("longitude") not in (None, "")
        ]
        return render_template("hotspots.html", hotspots=spots, reports=mapped, enough=bool(spots))

    @app.get("/trends")
    def road_trends():
        rows = reports.list_all()
        area = (request.args.get("area") or "").strip()
        scoped = [r for r in rows if area.lower() in area_key(r).lower()] if area else rows
        return render_template("trends.html", trend=monthly_timeline(scoped), area=area, count=len(scoped))

    @app.get("/nearby")
    def nearby():
        rows = reports.list_all()
        filtered, filters, types = apply_filters(rows, request.args)
        lat = lon = None
        nearby_rows = []
        try:
            lat = float(request.args.get("lat") or "")
            lon = float(request.args.get("lng") or request.args.get("lon") or "")
            radius = float(request.args.get("radius") or 2.5) * 1000
            nearby_rows = nearby_reports(lat, lon, filtered, radius_m=radius)
        except ValueError:
            nearby_rows = []
        return render_template(
            "nearby.html",
            reports=[public_report(r) for r in nearby_rows],
            types=types,
            filters=filters,
            has_origin=lat is not None and lon is not None,
        )

    @app.get("/compare")
    def compare():
        rows = reports.list_all()
        area_a = (request.args.get("area_a") or "").strip()
        area_b = (request.args.get("area_b") or "").strip()
        result = compare_areas(rows, area_a, area_b) if area_a and area_b else None
        names = sorted({area_key(r) for r in rows})
        return render_template("compare.html", result=result, area_a=area_a, area_b=area_b, names=names)

    @app.get("/improved")
    def improved_roads():
        rows = reports.list_all()
        return render_template("improved.html", result=most_improved_areas(rows))

    @app.post("/reports/<report_id>/verify")
    @login_required
    def verify_report(report_id: str):
        vote = request.form.get("vote", "")
        user = current_user()
        if not user:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        _updated, error = reports.add_verification(report_id, str(user["id"]), vote)
        if error:
            flash(error, "error")
        else:
            flash("Thank you. Your verification was recorded for administrators to review.", "success")
        return redirect(url_for("report_detail", report_id=report_id))

    @app.get("/admin/login")
    def admin_login():
        if current_admin():
            return redirect(url_for("admin_dashboard"))
        return render_template("admin/login.html", email="", next=request.args.get("next", ""))

    @app.get("/admin/register")
    def admin_register():
        flash("Public administrator registration is not available.", "error")
        return redirect(url_for("admin_login"))

    @app.post("/admin/register")
    def admin_register_post():
        flash("Public administrator registration is not available.", "error")
        return redirect(url_for("admin_login"))

    @app.post("/admin/login")
    def admin_login_post():
        from safe_street.auth import verify_password

        email = request.form.get("email", "")
        password = request.form.get("password", "")
        nxt = request.form.get("next") or request.args.get("next")
        user = users.find_by_email(email)
        if not user or not verify_password(user.get("password_hash", ""), password):
            flash("Invalid administrator email or password.", "error")
            return render_template("admin/login.html", email=email, next=nxt or "")
        if not is_admin_user(user):
            flash("This sign-in is for authorized administrators only.", "error")
            return render_template("admin/login.html", email=email, next=nxt or "")
        session.clear()
        session["user_id"] = str(user["id"])
        session["user_name"] = user.get("name") or ""
        session["role"] = "admin"
        session.permanent = True
        flash("Administrator session started.", "success")
        target = nxt if nxt and str(nxt).startswith("/admin") and not str(nxt).startswith("/admin/register") else url_for("admin_dashboard")
        return redirect(target)

    @app.get("/admin/logout")
    def admin_logout():
        session.clear()
        flash("Administrator signed out.", "success")
        return redirect(url_for("admin_login"))

    @app.get("/admin/dashboard")
    @admin_required
    def admin_dashboard():
        rows = attach_hazards(reports.list_all())
        stats = reports.stats_all()
        high = [public_report(r) for r in rows if str(r.get("severity") or "").lower() == "high"][:8]
        hazards = [public_report(r) for r in rows if (r.get("hazard") or {}).get("is_hazard")][:8]
        return render_template(
            "admin/dashboard.html",
            stats=stats,
            high=high,
            hazards=hazards,
            health=health_index(rows),
        )

    @app.get("/admin/reports")
    @admin_required
    def admin_reports():
        sort = request.args.get("sort") or "created_at"
        order = request.args.get("order") or "desc"
        rows = reports.list_all()
        filtered, filters, types = apply_filters(rows, request.args)
        reverse = order != "asc"
        if sort == "priority":
            rank = {"high": 0, "medium": 1, "low": 2}
            filtered.sort(key=lambda r: rank.get(str(r.get("severity") or "").lower(), 9), reverse=not reverse)
        elif sort == "status":
            filtered.sort(key=lambda r: str(r.get("status") or ""), reverse=reverse)
        else:
            filtered.sort(key=lambda r: str(r.get("created_at") or ""), reverse=reverse)
        page = paginate(filtered, int(request.args.get("page") or 1), 15)
        page["items"] = [admin_report(r) for r in page["items"]]
        return render_template(
            "admin/reports.html",
            page=page,
            filters=filters,
            types=types,
            sort=sort,
            order=order,
        )

    @app.get("/admin/reports/<report_id>")
    @admin_required
    def admin_report_detail(report_id: str):
        row = reports.get_by_id(report_id)
        if not row:
            abort(404)
        group = reports.list_group(row.get("issue_group_id") or "")
        next_statuses = ADMIN_TRANSITIONS.get(row.get("status") or "pending", ())
        return render_template(
            "admin/report_detail.html",
            report=admin_report(row),
            group=[public_report(r) for r in group],
            next_statuses=next_statuses,
            status_label=status_label,
        )

    @app.post("/admin/reports/<report_id>/status")
    @admin_required
    def admin_report_status(report_id: str):
        admin = current_admin()
        if not admin:
            flash("Administrator sign-in is required.", "error")
            return redirect(url_for("admin_login", next=request.path))
        status = request.form.get("status", "")
        reason = request.form.get("reason", "")
        if status == "resolved":
            flash("Use Confirm Resolution to mark a report resolved.", "error")
            return redirect(url_for("admin_report_detail", report_id=report_id))
        _updated, error = reports.append_status(report_id, status, str(admin["id"]), reason)
        flash(error or "Status updated.", "error" if error else "success")
        return redirect(url_for("admin_report_detail", report_id=report_id))

    @app.post("/admin/reports/<report_id>/resolve")
    @admin_required
    def admin_report_resolve(report_id: str):
        admin = current_admin()
        if not admin:
            flash("Administrator sign-in is required.", "error")
            return redirect(url_for("admin_login", next=request.path))
        description = request.form.get("description", "")
        file = request.files.get("after_image")
        after_rel = None
        if file and file.filename:
            if not allowed(file.filename, ALLOWED_IMAGE_EXT):
                flash("Please upload a JPG, PNG, BMP, or WebP repair photo.", "error")
                return redirect(url_for("admin_report_detail", report_id=report_id))
            path = storage.save_upload(file)
            after_rel = storage.public_relpath(path)
        _updated, error = reports.resolve(report_id, str(admin["id"]), description, after_rel)
        flash(error or "Report marked resolved with repair evidence.", "error" if error else "success")
        return redirect(url_for("admin_report_detail", report_id=report_id))

    @app.post("/admin/reports/<report_id>/reopen")
    @admin_required
    def admin_report_reopen(report_id: str):
        admin = current_admin()
        if not admin:
            flash("Administrator sign-in is required.", "error")
            return redirect(url_for("admin_login", next=request.path))
        reason = request.form.get("reason", "")
        _updated, error = reports.reopen(report_id, str(admin["id"]), reason)
        flash(error or "Issue reopened and returned to review.", "error" if error else "success")
        return redirect(url_for("admin_report_detail", report_id=report_id))

    @app.get("/admin/analytics")
    @admin_required
    def admin_analytics():
        rows = reports.list_all()
        filtered, filters, types = apply_filters(rows, request.args)
        from database.reports import summarize_reports

        stats = summarize_reports(filtered)
        return render_template(
            "admin/analytics.html",
            stats=stats,
            health=health_index(filtered),
            spots=hotspots(filtered),
            filters=filters,
            types=types,
        )

    @app.get("/admin/high-priority")
    @admin_required
    def admin_high_priority():
        return redirect(url_for("admin_reports", severity="high"))

    @app.get("/admin/verification")
    @admin_required
    def admin_verification():
        return redirect(url_for("admin_analytics"))

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403
