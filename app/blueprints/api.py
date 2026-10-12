"""
app/blueprints/api.py
JSON API endpoints consumed by live.js and admin.js.

Security controls:
- @login_required on all endpoints
- IDOR: /api/complaints returns only the current user's data for students
- Status update POST requires valid CSRF token (Flask-WTF exemption NOT set)
- Server-side state-machine validation on status changes
- Returns JSON errors (no HTML stack traces)
"""

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required

from app.models import (
    get_all_complaints,
    get_complaint_by_id,
    get_complaint_stats,
    get_complaints_by_user,
    update_complaint_status,
)
from app.security import audit, role_required
from app.validators import validate_status_transition

api_bp = Blueprint("api", __name__)


@api_bp.route("/complaints")
@login_required
def complaints():
    """
    GET /api/complaints
    Students: returns their own complaints only (IDOR protection).
    Admins: returns all complaints plus aggregate stats.
    Polled every 5 seconds by live.js.
    """
    if current_user.role == "admin":
        status_filter = request.args.get("status", "").strip()
        category_filter = request.args.get("category", "").strip()
        status_q = status_filter if status_filter in {"Pending", "In Progress", "Resolved"} else None
        category_q = category_filter if category_filter in {"Hostel", "Lab", "Academic", "Harassment", "Other"} else None

        rows = get_all_complaints(status=status_q, category=category_q)
        stats = get_complaint_stats()
        return jsonify(
            complaints=_serialize_complaints(rows),
            stats=stats,
        )
    else:
        # Security: IDOR — scoped to current_user.id inside the query
        rows = get_complaints_by_user(current_user.id)
        return jsonify(complaints=_serialize_complaints(rows))


@api_bp.route("/complaints/<int:complaint_id>/status", methods=["POST"])
@login_required
@role_required("admin")
def update_status(complaint_id: int):
    """
    POST /api/complaints/<id>/status
    Body (JSON): { "status": "In Progress" }
    Requires CSRF token header: X-CSRFToken.
    Admin only. Validates state-machine transition server-side.
    """
    data = request.get_json(silent=True) or {}
    new_status = data.get("status", "").strip()

    complaint = get_complaint_by_id(complaint_id)
    if complaint is None:
        return jsonify(error="Complaint not found."), 404

    # Security: state-machine validation — prevents invalid transitions
    err = validate_status_transition(complaint["status"], new_status)
    if err:
        return jsonify(error=err), 400

    update_complaint_status(complaint_id, new_status)
    audit(
        action="status_changed",
        detail=f"Complaint #{complaint_id}: {complaint['status']} -> {new_status}",
        user_id=current_user.id,
    )

    return jsonify(success=True, complaint_id=complaint_id, new_status=new_status)


def _serialize_complaints(rows) -> list:
    """Convert sqlite3.Row objects to plain dicts for JSON serialisation."""
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "description": r["description"],
            "status": r["status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            # student_name only present in admin query
            "student_name": r["student_name"] if "student_name" in r.keys() else None,
        })
    return result
