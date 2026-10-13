"""
app/blueprints/complaints.py
Student-facing complaint routes.

Security controls:
- @login_required: unauthenticated users redirected to login
- @role_required("student"): admins cannot use student routes
- IDOR protection: get_complaints_by_user() always filters by current_user.id
- Server-side validation on all complaint fields
- Audit log entry on complaint creation
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.models import (
    create_complaint,
    get_complaints_by_user,
)
from app.security import audit, role_required
from app.validators import (
    validate_category,
    validate_complaint_description,
    validate_complaint_title,
)

complaints_bp = Blueprint("complaints", __name__)

CATEGORIES = ["Hostel", "Lab", "Academic", "Harassment", "Other"]


@complaints_bp.route("/dashboard")
@login_required
@role_required("student")
def dashboard():
    """Student dashboard showing only their own complaints."""
    # Security: IDOR protection — query scoped to current_user.id
    complaints = get_complaints_by_user(current_user.id)
    return render_template("dashboard.html", complaints=complaints)


@complaints_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("student")
def new_complaint():
    """Submit a new complaint."""
    errors = {}
    form_data = {}

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        form_data = {"title": title, "category": category, "description": description}

        # Server-side validation — Security: whitelist category, length-check all fields
        if err := validate_complaint_title(title):
            errors["title"] = err
        if err := validate_category(category):
            errors["category"] = err
        if err := validate_complaint_description(description):
            errors["description"] = err

        if not errors:
            cid = create_complaint(current_user.id, title, category, description)
            audit(
                action="complaint_created",
                detail=f"Complaint #{cid}: {title[:50]}",
                user_id=current_user.id,
            )
            flash("Complaint submitted successfully.", "success")
            return redirect(url_for("complaints.dashboard"))

    return render_template(
        "new_complaint.html",
        errors=errors,
        form_data=form_data,
        categories=CATEGORIES,
    )
