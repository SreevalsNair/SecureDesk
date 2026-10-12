"""
app/config.py
Configuration classes for SecureDesk.
Reads every sensitive value from environment variables — nothing is hardcoded.
"""

import os
from datetime import timedelta


class BaseConfig:
    """Shared defaults across all environments."""

    # ── Session ──────────────────────────────────────────────────────────────
    # Security: short lifetime limits the window of a stolen cookie
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True          # Security: JS cannot read the cookie
    SESSION_COOKIE_SAMESITE = "Lax"        # Security: CSRF mitigation
    SESSION_COOKIE_NAME = "sd_session"

    # ── Flask-WTF CSRF ────────────────────────────────────────────────────────
    WTF_CSRF_ENABLED = True                 # Security: CSRF on all state-changing forms
    WTF_CSRF_TIME_LIMIT = 1800             # 30 min — matches session lifetime

    # ── Flask-Limiter ─────────────────────────────────────────────────────────
    RATELIMIT_DEFAULT = "200 per minute"   # Global default; stricter per-route overrides below
    RATELIMIT_STORAGE_URI = "memory://"    # Per-worker; DB lockout is the authoritative control
    RATELIMIT_HEADERS_ENABLED = True

    # ── App settings ──────────────────────────────────────────────────────────
    DB_PATH = os.environ.get("DB_PATH", "securedesk.db")
    LOG_DIR = os.environ.get("LOG_DIR", "logs")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")

    # Never log the actual password; manage.py reads ADMIN_PASSWORD directly
    ADMIN_PASSWORD_ENV = "ADMIN_PASSWORD"

    MAX_CONTENT_LENGTH = 1 * 1024 * 1024   # 1 MB upload cap


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False           # HTTP is fine locally

    # Dev secret — overridden by .env in practice
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-placeholder-change-me")


class ProductionConfig(BaseConfig):
    DEBUG = False                           # Security: never expose tracebacks
    TESTING = False

    # Secure must be True in prod (set SESSION_COOKIE_SECURE=true in .env)
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    @classmethod
    def validate(cls):
        """Called at startup — refuses to run with missing or placeholder secrets."""
        key = os.environ.get("SECRET_KEY", "")
        placeholder = "dev-insecure-placeholder-change-me"
        if not key or key == placeholder:
            raise RuntimeError(
                "FATAL: SECRET_KEY is missing or is the placeholder value. "
                "Set a strong random value in your .env file before running in production."
            )
        cls.SECRET_KEY = key


class TestingConfig(BaseConfig):
    DEBUG = False
    TESTING = True
    WTF_CSRF_ENABLED = False               # Disabled in tests; CSRF tested separately
    SESSION_COOKIE_SECURE = False
    SECRET_KEY = "test-secret-key-not-for-production"
    DB_PATH = ":memory:"                   # Use in-memory SQLite for isolated tests
    RATELIMIT_ENABLED = False              # Disable rate limits in tests unless testing them


# Map string name -> class (used by create_app)
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
