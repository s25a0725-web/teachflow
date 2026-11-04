# -*- coding: utf-8 -*-
"""TeachFlow application factory and entry point."""
import os
import secrets as _secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, session, jsonify, request, redirect, url_for, flash
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

from db import init_db, get_setting
from i18n import t, LANGUAGES, day_names

csrf = CSRFProtect()

_SECRET_FILE = Path(__file__).resolve().parent / ".secret_key"


def _default_secret():
    """Return a stable per-install secret so sessions survive restarts.

    Used only when TEACHFLOW_SECRET is not set. The key is generated once and
    persisted to a gitignored file, which is far stronger than the previous
    hardcoded fallback.
    """
    try:
        if _SECRET_FILE.exists():
            key = _SECRET_FILE.read_text(encoding="utf-8").strip()
            if key:
                return key
    except OSError:
        pass
    key = _secrets.token_hex(32)
    try:
        _SECRET_FILE.write_text(key, encoding="utf-8")
    except OSError:
        pass
    return key


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("TEACHFLOW_SECRET") or _default_secret()
    # No upload quota: file size is limited only by the machine's disk, never by the app.
    app.config["MAX_CONTENT_LENGTH"] = None

    # Session hardening
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("TEACHFLOW_HTTPS") == "1"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

    # CSRF protection (set TEACHFLOW_CSRF=0 only for the broad smoke test)
    app.config["WTF_CSRF_ENABLED"] = os.environ.get("TEACHFLOW_CSRF", "1") == "1"
    csrf.init_app(app)

    init_db()

    from auth import bp as auth_bp
    from views import bp as views_bp
    from documents import bp as documents_bp
    from studio import bp as studio_bp
    from study import bp as study_bp
    from analytics import bp as analytics_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(views_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(studio_bp)
    app.register_blueprint(study_bp)
    app.register_blueprint(analytics_bp)

    @app.context_processor
    def inject_globals():
        return {
            "t": t,
            "LANGUAGES": LANGUAGES,
            "day_names": day_names,
            "lang": session.get("lang", "en"),
            "brand_name": get_setting("school_name") or "SJK(T) Sepang",
            "brand_tagline": get_setting("tagline") or t("tagline", session.get("lang", "en")),
            "theme": get_setting("theme") or "default",
            "bg_image": get_setting("bg_image") or "",
        }

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if request.is_json or request.path.startswith(("/chatbot", "/studio", "/study")):
            return jsonify({"error": "csrf"}), 400
        flash("csrf_failed", "error")
        return redirect(request.referrer or url_for("auth.login"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
