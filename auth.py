# -*- coding: utf-8 -*-
"""Authentication blueprint: register, login, logout."""
from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db

bp = Blueprint("auth", __name__, url_prefix="")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        name = request.form["name"].strip()
        password = request.form["password"]
        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            db.close()
            flash("email_exists", "error")
            return redirect(url_for("auth.register"))
        count = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        role = "admin" if count == 0 else "teacher"
        db.execute(
            "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)",
            (email, generate_password_hash(password), name, role),
        )
        db.commit()
        db.close()
        flash("registered", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()
        if user and check_password_hash(user["password_hash"], password):
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
