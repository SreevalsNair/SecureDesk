"""
app/blueprints/main.py
Minimal routes: home redirect and /health endpoint.
"""

from flask import Blueprint, jsonify, redirect, url_for
from flask_login import current_user

from app.db import get_db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Redirect authenticated users to their dashboard."""
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("complaints.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/health")
def health():
    """
    Health-check endpoint for load balancers and monitoring.
    Verifies the database is reachable before returning ok.
    """
    try:
        get_db().execute("SELECT 1")
        return jsonify(status="ok"), 200
    except Exception as exc:
        return jsonify(status="error", detail=str(exc)), 500
