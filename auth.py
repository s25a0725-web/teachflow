# -*- coding: utf-8 -*-
"""Authentication blueprint: register, login, logout."""
from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db
import userstore

bp = Blueprint("auth", __name__, url_prefix="")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        name = request.form["name"].strip()
        password = request.form["password"]
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
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = userstore.get_by_email(email)
        if userstore.check(user, password):
            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["name"] = user["name"]
            session["lang"] = session.get("lang", "en")
            return redirect(url_for("views.dashboard"))
        flash("invalid_login", "error")
        return redirect(url_for("auth.login"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


# --------------------------------------------------------------------------
# Reset password (self-service, security-question based — no email needed)
# --------------------------------------------------------------------------
SECURITY_QUESTIONS = ("sq_pet", "sq_school", "sq_city", "sq_mother")


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = userstore.get_by_email(email)
        if user is None:
            flash("reset_email_unknown", "error")
            return redirect(url_for("auth.forgot_password"))
        if not user["security_question"] or not user["security_answer_hash"]:
            flash("reset_no_question", "error")
            return redirect(url_for("auth.forgot_password"))
        session["reset_user_id"] = user["id"]
        return redirect(url_for("auth.reset_password"))
    return render_template("forgot_password.html")


@bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    uid = session.get("reset_user_id")
    if not uid:
        return redirect(url_for("auth.forgot_password"))
    user = userstore.get_by_id(uid)
    if user is None or not user["security_question"]:
        session.pop("reset_user_id", None)
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        answer = request.form.get("answer", "").strip()
        password = request.form.get("password", "")
        if not answer or not check_password_hash(user["security_answer_hash"], answer):
            flash("reset_wrong_answer", "error")
            return redirect(url_for("auth.reset_password"))
        if len(password) < 6:
            flash("reset_short", "error")
            return redirect(url_for("auth.reset_password"))
        userstore.update_password(uid, password)
        session.pop("reset_user_id", None)
        flash("reset_done", "success")
        return redirect(url_for("auth.login"))
    return render_template("reset_password.html", question=user["security_question"])


# --------------------------------------------------------------------------
# Parent accounts (separate login)
# --------------------------------------------------------------------------
@bp.route("/parent-register", methods=["GET", "POST"])
def parent_register():
    if request.method == "POST":
        name = request.form["name"].strip()
        ic_number = request.form.get("ic_number", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form["password"]
        if not ic_number and not email:
            flash("gen_empty", "error")
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
        identifier = request.form["identifier"].strip().lower()
        password = request.form["password"]
        db = get_db()
        p = db.execute(
            "SELECT * FROM parent_accounts WHERE "
            "(ic_number IS NOT NULL AND lower(ic_number)=lower(?)) "
            "OR (email IS NOT NULL AND lower(email)=lower(?))",
            (identifier, identifier),
        ).fetchone()
        db.close()
        if p and check_password_hash(p["password_hash"], password):
            session.clear()
            session["parent_id"] = p["id"]
            session["parent_name"] = p["name"]
            session["parent_email"] = p["email"] or ""
            session["parent_ic"] = p["ic_number"] or ""
            session["lang"] = session.get("lang", "en")
            return redirect(url_for("views.parent_dashboard"))
        flash("invalid_login", "error")
        return redirect(url_for("auth.parent_login"))
    return render_template("parent_login.html")


@bp.route("/parent-logout")
def parent_logout():
    session.clear()
    return redirect(url_for("auth.parent_login"))
