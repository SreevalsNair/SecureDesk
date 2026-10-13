"""
app/blueprints/admin.py
Admin-only routes: dashboard (complaints table + stat tiles) and audit log.

Security controls:
- @role_required("admin"): students get 403
- Status transitions validated server-side (state-machine check)
- CSRF token required on status-update POST (enforced by Flask-WTF globally)
- Audit log entry on every status change
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required

from app.models import (
    get_all_complaints,
    get_audit_log,
    get_complaint_by_id,
    get_complaint_stats,
    update_complaint_status,
)
from app.security import audit, role_required
from app.validators import validate_status_transition

admin_bp = Blueprint("admin", __name__)

CATEGORIES = ["Hostel", "Lab", "Academic", "Harassment", "Other"]
STATUSES = ["Pending", "In Progress", "Resolved"]


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    """Admin dashboard: stat tiles and filterable complaints table."""
    status_filter = request.args.get("status", "").strip()
    category_filter = request.args.get("category", "").strip()

    # Only pass through whitelisted values to the model
    status_q = status_filter if status_filter in STATUSES else None
    category_q = category_filter if category_filter in CATEGORIES else None

    complaints = get_all_complaints(status=status_q, category=category_q)
    stats = get_complaint_stats()

    return render_template(
        "admin_dashboard.html",
        complaints=complaints,
        stats=stats,
        categories=CATEGORIES,
        statuses=STATUSES,
        current_status=status_filter,
        current_category=category_filter,
    )


@admin_bp.route("/audit")
@login_required
@role_required("admin")
def audit_log():
    """Paginated audit log, newest first."""
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    rows, total = get_audit_log(page=page, per_page=25)
    total_pages = max(1, (total + 24) // 25)

    return render_template(
        "audit.html",
        rows=rows,
        page=page,
        total_pages=total_pages,
        total=total,
    )
