<<<<<<< HEAD
"""Authentication routes for SarvSathi (register/login)."""
=======
"""Authentication routes for Aira (register/login)."""
>>>>>>> master

from __future__ import annotations

import bcrypt
from flask import Blueprint, jsonify, request, session

from db import create_user, get_user


auth_bp = Blueprint("auth", __name__)


def hash_password(password: str) -> str:
    """Hash plaintext password using bcrypt."""
    pw = (password or "").encode("utf-8")
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    try:
        return bcrypt.checkpw(
            (password or "").encode("utf-8"),
            (password_hash or "").encode("utf-8"),
        )
    except Exception:
        return False


@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"ok": False, "error": "username and password are required"}), 400

    if len(password) < 6:
        return jsonify({"ok": False, "error": "password must be at least 6 characters"}), 400

    password_hash = hash_password(password)
    user_id = create_user(username, password_hash)
    if user_id is None:
        return jsonify({"ok": False, "error": "username already exists"}), 409

    session["user_id"] = user_id
    session["username"] = username
    return jsonify({"ok": True, "user": {"id": user_id, "username": username}}), 201


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"ok": False, "error": "username and password are required"}), 400

    user = get_user(username)
    if not user:
        return jsonify({"ok": False, "error": "invalid credentials"}), 401

    if not verify_password(password, user.get("password_hash", "")):
        return jsonify({"ok": False, "error": "invalid credentials"}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]

    return jsonify({"ok": True, "user": {"id": user["id"], "username": user["username"]}}), 200


@auth_bp.route("/api/me", methods=["GET"])
def me():
    user_id = session.get("user_id")
    username = session.get("username")
    if not user_id:
        return jsonify({"ok": False, "authenticated": False}), 401
    return jsonify({
        "ok": True,
        "authenticated": True,
        "user": {"id": user_id, "username": username},
    })


@auth_bp.route("/api/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return jsonify({"ok": True, "message": "logged out"})
