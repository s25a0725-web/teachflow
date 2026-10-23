# -*- coding: utf-8 -*-
"""TeachFlow application factory and entry point."""
import os

from flask import Flask, session

from db import init_db, get_setting
from i18n import t, LANGUAGES, day_names


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("TEACHFLOW_SECRET", "dev-secret-change-me")
    # No upload quota: file size is limited only by the machine's disk, never by the app.
    app.config["MAX_CONTENT_LENGTH"] = None

    init_db()

    from auth import bp as auth_bp
    from views import bp as views_bp
    from documents import bp as documents_bp
    from studio import bp as studio_bp
    from study import bp as study_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(views_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(studio_bp)
    app.register_blueprint(study_bp)

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

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
