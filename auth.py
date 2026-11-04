# -*- coding: utf-8 -*-
"""Authentication blueprint: register, login, logout, password reset, parents."""
import re
import time

from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db
import userstore
from security import is_blocked, record

bp = Blueprint("auth", __name__, url_prefix="")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SECURITY_QUESTIONS = ("sq_pet", "sq_school", "sq_city", "sq_mother")

# Rate-limit windows (in-memory, per-process)
_LOGIN_IP_LIMIT = 20
_LOGIN_IP_WINDOW = 600
_LOGIN_ACCT_LIMIT = 5
_LOGIN_ACCT_WINDOW = 300
_RESET_LIMIT = 10
_RESET_WINDOW = 600
_RESET_SESSION_SECONDS = 900  # reset link valid for 15 minutes


def _ip():
    fwd = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return request.remote_addr or fwd or "0.0.0.0"


def _valid_email(email):
    return bool(_EMAIL_RE.match((email or "").strip()))


def _set_user_session(user, remember=False):
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session["name"] = user["name"]
    session["lang"] = session.get("lang", "en")
    session.permanent = bool(remember)


def _set_parent_session(parent, remember=False):
    session.clear()
    session["parent_id"] = parent["id"]
    session["parent_name"] = parent["name"]
    session["parent_email"] = parent["email"] or ""
    session["parent_ic"] = parent["ic_number"] or ""
    session["lang"] = session.get("lang", "en")
    session.permanent = bool(remember)


def _login_blocked(email):
    return (
        is_blocked(f"login:ip:{_ip()}", _LOGIN_IP_LIMIT, _LOGIN_IP_WINDOW)
        or (email and is_blocked(f"login:acct:{email}", _LOGIN_ACCT_LIMIT, _LOGIN_ACCT_WINDOW))
    )


def _record_login_failure(email):
    record(f"login:ip:{_ip()}")
    if email:
        record(f"login:acct:{email}")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        if not name:
            flash("name_required", "error")
            return redirect(url_for("auth.register"))
        if not _valid_email(email):
            flash("invalid_email", "error")
            return redirect(url_for("auth.register"))
        if len(password) < 6:
            flash("reset_short", "error")
            return redirect(url_for("auth.register"))
        if userstore.get_by_email(email):
            flash("email_exists", "error")
            return redirect(url_for("auth.register"))
        role = "admin" if userstore.count() == 0 else "teacher"
        userstore.add(
            email=email,
            password=password,
            name=name,
            role=role,
            security_question=request.form.get("security_question", "").strip() or None,
            security_answer=request.form.get("security_answer", "").strip() or None,
        )
        flash("registered", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"
        if _login_blocked(email):
            flash("too_many_attempts", "error")
            return redirect(url_for("auth.login"))
        user = userstore.get_by_email(email) if _valid_email(email) else None
        if user is None or not userstore.check(user, password):
            _record_login_failure(email)
            flash("invalid_login", "error")
            return redirect(url_for("auth.login"))
        _set_user_session(user, remember)
        return redirect(url_for("views.dashboard"))
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


# --------------------------------------------------------------------------
# Reset password (self-service, security-question based — no email needed)
# --------------------------------------------------------------------------
@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        if is_blocked(f"reset:{_ip()}", _RESET_LIMIT, _RESET_WINDOW):
            flash("too_many_attempts", "error")
            return redirect(url_for("auth.forgot_password"))
        email = request.form.get("email", "").strip().lower()
        user = userstore.get_by_email(email)
        if user is None:
            record(f"reset:{_ip()}")
            flash("reset_email_unknown", "error")
            return redirect(url_for("auth.forgot_password"))
        if not user.get("security_question") or not user.get("security_answer_hash"):
            flash("reset_no_question", "error")
            return redirect(url_for("auth.forgot_password"))
        session["reset_user_id"] = user["id"]
        session["reset_expires"] = time.time() + _RESET_SESSION_SECONDS
        return redirect(url_for("auth.reset_password"))
    return render_template("forgot_password.html")


@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    uid = session.get("reset_user_id")
    expires = session.get("reset_expires", 0)
    if not uid or time.time() > expires:
        session.pop("reset_user_id", None)
        session.pop("reset_expires", None)
        return redirect(url_for("auth.forgot_password"))
    user = userstore.get_by_id(uid)
    if user is None or not user.get("security_question"):
        session.pop("reset_user_id", None)
        session.pop("reset_expires", None)
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        if is_blocked(f"reset:{_ip()}", _RESET_LIMIT, _RESET_WINDOW):
            flash("too_many_attempts", "error")
            return redirect(url_for("auth.reset_password"))
        answer = request.form.get("answer", "").strip()
        password = request.form.get("password", "")
        if not answer or not check_password_hash(user["security_answer_hash"], answer):
            record(f"reset:{_ip()}")
            flash("reset_wrong_answer", "error")
            return redirect(url_for("auth.reset_password"))
        if len(password) < 6:
            flash("reset_short", "error")
            return redirect(url_for("auth.reset_password"))
        userstore.update_password(uid, password)
        session.pop("reset_user_id", None)
        session.pop("reset_expires", None)
        flash("reset_done", "success")
        return redirect(url_for("auth.login"))
    return render_template("reset_password.html", question=user["security_question"])


# --------------------------------------------------------------------------
# Parent accounts (separate login)
# --------------------------------------------------------------------------
@bp.route("/parent-register", methods=["GET", "POST"])
def parent_register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        ic_number = request.form.get("ic_number", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name:
            flash("name_required", "error")
            return redirect(url_for("auth.parent_register"))
        if email and not _valid_email(email):
            flash("invalid_email", "error")
            return redirect(url_for("auth.parent_register"))
        if not ic_number and not email:
            flash("gen_empty", "error")
            return redirect(url_for("auth.parent_register"))
        if len(password) < 6:
            flash("reset_short", "error")
            return redirect(url_for("auth.parent_register"))
        db = get_db()
        if ic_number:
            existing = db.execute("SELECT id FROM parent_accounts WHERE ic_number=?", (ic_number,)).fetchone()
            if existing:
                db.close()
                flash("email_exists", "error")
                return redirect(url_for("auth.parent_register"))
        if email:
            existing = db.execute("SELECT id FROM parent_accounts WHERE lower(email)=lower(?)", (email,)).fetchone()
            if existing:
                db.close()
                flash("email_exists", "error")
                return redirect(url_for("auth.parent_register"))
        db.execute(
            "INSERT INTO parent_accounts (email, ic_number, password_hash, name) VALUES (?, ?, ?, ?)",
            (email or None, ic_number or None, generate_password_hash(password), name),
        )
        db.commit()
        db.close()
        flash("registered", "success")
        return redirect(url_for("auth.parent_login"))
    return render_template("parent_register.html")


@bp.route("/parent-login", methods=["GET", "POST"])
def parent_login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"
        if is_blocked(f"login:ip:{_ip()}", _LOGIN_IP_LIMIT, _LOGIN_IP_WINDOW) or (
            identifier and is_blocked(f"login:parent:{identifier}", _LOGIN_ACCT_LIMIT, _LOGIN_ACCT_WINDOW)
        ):
            flash("too_many_attempts", "error")
            return redirect(url_for("auth.parent_login"))
        db = get_db()
        p = db.execute(
            "SELECT * FROM parent_accounts WHERE "
            "(ic_number IS NOT NULL AND lower(ic_number)=lower(?)) "
            "OR (email IS NOT NULL AND lower(email)=lower(?))",
            (identifier, identifier),
        ).fetchone()
        db.close()
        if p and check_password_hash(p["password_hash"], password):
            _set_parent_session(p, remember)
            return redirect(url_for("views.parent_dashboard"))
        if identifier:
            record(f"login:ip:{_ip()}")
            record(f"login:parent:{identifier}")
        flash("invalid_login", "error")
        return redirect(url_for("auth.parent_login"))
    return render_template("parent_login.html")


@bp.route("/parent-logout", methods=["POST"])
def parent_logout():
    session.clear()
    return redirect(url_for("auth.parent_login"))
