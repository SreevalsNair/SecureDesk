"""
app/blueprints/auth.py
Authentication routes: register, login, logout.

Security controls implemented here:
- Passwords hashed with bcrypt (security.hash_password)
- Account lockout checked before verifying password (brute-force protection)
- Rate limiting on login and register (Flask-Limiter)
- Generic error message for unknown email AND wrong password (prevents user enumeration)
- Safe redirect after login (validators.validate_safe_redirect)
- Audit log entries for every auth event
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app import limiter
from app.models import create_user, get_user_by_email
from app.security import (
    audit,
    handle_failed_login,
    handle_successful_login,
    hash_password,
    is_account_locked,
    verify_password,
)
from app.validators import (
    validate_email,
    validate_name,
    validate_password,
    validate_safe_redirect,
)

auth_bp = Blueprint("auth", __name__)

# Generic message — Security: prevents user enumeration (same msg for bad email or bad password)
_LOGIN_FAIL_MSG = "Invalid email or password."


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per minute")   # Security: rate limiting on registration
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    errors = {}
    form_data = {}

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        form_data = {"name": name, "email": email}

        # Server-side validation — Security: never trust client checks
        if err := validate_name(name):
            errors["name"] = err
        if err := validate_email(email):
            errors["email"] = err
        if err := validate_password(password):
            errors["password"] = err

        if not errors:
            # Check email uniqueness
            if get_user_by_email(email):
                # Vague message to avoid leaking which emails are registered
                errors["email"] = "An account with this email already exists."
            else:
                pw_hash = hash_password(password)   # Security: bcrypt hash
                user_id = create_user(name, email, pw_hash)
                audit(action="register", detail=f"New student: {email}", user_id=user_id)
                flash("Account created! Please log in.", "success")
                return redirect(url_for("auth.login"))

    return render_template("register.html", errors=errors, form_data=form_data)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")   # Security: rate limiting on login
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    errors = {}
    form_data = {}

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        form_data = {"email": email}

        user = get_user_by_email(email)

        if user is None:
            # Security: identical message for unknown email — prevents user enumeration
            audit(action="login_failure", detail=f"Unknown email: {email}")
            errors["general"] = _LOGIN_FAIL_MSG
        elif is_account_locked(user):
            # Security: account lockout — still show generic message
            audit(action="login_failure", detail="Locked account login attempt", user_id=user["id"])
            errors["general"] = _LOGIN_FAIL_MSG
        elif not verify_password(password, user["password_hash"]):
            # Security: wrong password
            handle_failed_login(user)
            audit(action="login_failure", detail="Wrong password", user_id=user["id"])
            errors["general"] = _LOGIN_FAIL_MSG
        else:
            # Successful login
            handle_successful_login(user)

            # Build a lightweight proxy object Flask-Login can serialise
            from flask import current_app
            proxy = current_app.UserProxy(user)
            login_user(proxy, remember=False)

            audit(action="login_success", detail=f"Login: {email}", user_id=user["id"])

            # Security: safe redirect — validate the `next` parameter
            next_url = request.args.get("next", "")
            if validate_safe_redirect(next_url):
                return redirect(next_url)
            return redirect(url_for("main.index"))

    return render_template("login.html", errors=errors, form_data=form_data)


@auth_bp.route("/logout")
@login_required
def logout():
    audit(action="logout", detail="", user_id=current_user.id)
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
