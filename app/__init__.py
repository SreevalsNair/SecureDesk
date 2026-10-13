"""
app/__init__.py
Application factory for SecureDesk.
Creates the Flask app, registers extensions, blueprints, security headers,
error handlers, and logging.  Extensions are initialised here and imported
by blueprints — avoids circular imports.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import config_map

# ─────────────────────────────────────────────────────────────────────────────
# Extensions — created once here, initialised inside create_app()
# ─────────────────────────────────────────────────────────────────────────────

login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_name: str = None) -> Flask:
    """
    Application factory.
    :param config_name: 'development' | 'production' | 'testing'
                        Falls back to the FLASK_ENV environment variable,
                        then 'development'.
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    config_cls = config_map.get(config_name, config_map["development"])

    # Validate secrets before serving any request in production
    if config_name == "production" and hasattr(config_cls, "validate"):
        config_cls.validate()

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_cls)

    # ── ProxyFix: trust one Nginx hop so REMOTE_ADDR is the real client IP ──
    # Security: needed for rate-limiting and audit logging behind a reverse proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # ── Initialise extensions ─────────────────────────────────────────────────
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    csrf.init_app(app)     # Security: CSRF protection on all state-changing forms
    limiter.init_app(app)  # Security: rate limiting

    # ── Database teardown ────────────────────────────────────────────────────
    from app.db import close_db
    app.teardown_appcontext(close_db)

    # ── Flask-Login user loader ───────────────────────────────────────────────
    from app.models import get_user_by_id

    class UserProxy:
        """Minimal user object stored in session; implements Flask-Login interface."""
        def __init__(self, row):
            self.id = row["id"]
            self.name = row["name"]
            self.email = row["email"]
            self.role = row["role"]
            self.is_authenticated = True
            self.is_active = True
            self.is_anonymous = False

        def get_id(self):
            return str(self.id)

    # Store UserProxy class on app so blueprints can import it cleanly
    app.UserProxy = UserProxy

    @login_manager.user_loader
    def load_user(user_id):
        row = get_user_by_id(int(user_id))
        if row is None:
            return None
        return UserProxy(row)

    # ── Register blueprints ───────────────────────────────────────────────────
    from app.blueprints.main import main_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.complaints import complaints_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(complaints_bp, url_prefix="/complaints")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")

    # ── Security headers on every response ───────────────────────────────────
    # Security: defence-in-depth against XSS, clickjacking, MIME sniffing
    @app.after_request
    def set_security_headers(response):
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Frame-Options"] = "DENY"            # Clickjacking
        response.headers["X-Content-Type-Options"] = "nosniff"  # MIME sniffing
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        # HSTS only when HTTPS is active (controlled by env var)
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    # ── Error handlers ────────────────────────────────────────────────────────
    # Security: no stack traces exposed to the client
    def _error_page(code: int, title: str, message: str):
        if request.path.startswith("/api/"):
            return jsonify(error=message), code
        return render_template("error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(e):
        return _error_page(400, "Bad Request", "The request could not be understood.")

    @app.errorhandler(403)
    def forbidden(e):
        return _error_page(403, "Access Denied", "You do not have permission to view this page.")

    @app.errorhandler(404)
    def not_found(e):
        return _error_page(404, "Page Not Found", "The page you requested does not exist.")

    @app.errorhandler(429)
    def too_many_requests(e):
        return _error_page(429, "Too Many Requests", "You are making requests too quickly. Please wait a moment and try again.")

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error("500 error: %s", e)
        return _error_page(500, "Server Error", "Something went wrong on our end. Please try again later.")

    # ── Application logging ───────────────────────────────────────────────────
    _configure_logging(app)

    return app


def _configure_logging(app: Flask) -> None:
    """
    Set up a rotating file log.
    Security: never log passwords, tokens, or session data.
    """
    log_dir = app.config.get("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, "securedesk.log")
    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    )
    handler.setLevel(logging.INFO)

    # Attach to both the Flask app logger and the root logger
    app.logger.addHandler(handler)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

    app.logger.info("SecureDesk starting — env=%s", os.environ.get("FLASK_ENV", "development"))
