"""
app/security.py
Security utilities for SecureDesk:
  - Password hashing with bcrypt (no plaintext stored anywhere)
  - Account lockout logic (5 failed attempts -> 15-minute ban)
  - role_required decorator (RBAC — privilege escalation / IDOR protection)
  - audit() convenience helper (wraps models.create_audit_entry)
"""

from __future__ import annotations

import functools
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from flask import abort, request
from flask_login import current_user

from app import models

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

LOCKOUT_THRESHOLD = 5          # Fail attempts before lock
LOCKOUT_DURATION_MINUTES = 15  # Duration of the lock


# ─────────────────────────────────────────────────────────────────────────────
# Password hashing — Security: passwords never stored in plaintext
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(plaintext: str) -> str:
    """Hash a password with bcrypt (work factor 12). Returns a UTF-8 string."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plaintext.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    """Constant-time comparison via bcrypt — Security: prevents timing attacks."""
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Account lockout — Security: brute-force / credential-stuffing protection
# ─────────────────────────────────────────────────────────────────────────────

def is_account_locked(user_row) -> bool:
    """Return True if the account is currently locked."""
    if not user_row["locked_until"]:
        return False
    locked_until = datetime.fromisoformat(user_row["locked_until"]).replace(
        tzinfo=timezone.utc
    )
    return datetime.now(timezone.utc) < locked_until


def handle_failed_login(user_row) -> None:
    """Increment failed attempts; lock the account if threshold is reached."""
    new_count = user_row["failed_attempts"] + 1
    models.increment_failed_attempts(user_row["id"])
    if new_count >= LOCKOUT_THRESHOLD:
        until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        models.set_lockout(user_row["id"], until.isoformat())
        audit(
            action="lockout",
            detail=f"Account locked after {new_count} failed attempts",
            user_id=user_row["id"],
        )
        logger.warning("Account locked: user_id=%s ip=%s", user_row["id"], _client_ip())


def handle_successful_login(user_row) -> None:
    """Clear lockout state after a successful authentication."""
    models.reset_failed_attempts(user_row["id"])


# ─────────────────────────────────────────────────────────────────────────────
# Role-based access — Security: prevents privilege escalation
# ─────────────────────────────────────────────────────────────────────────────

def role_required(*roles: str):
    """
    Decorator that restricts a view to users with one of the given roles.
    Usage:  @role_required("admin")
    Returns HTTP 403 and logs an audit entry on access denied.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if current_user.role not in roles:
                audit(
                    action="access_denied",
                    detail=f"User tried to access {request.path} (role={current_user.role})",
                    user_id=current_user.id,
                )
                logger.warning(
                    "Access denied: user_id=%s role=%s path=%s",
                    current_user.id,
                    current_user.role,
                    request.path,
                )
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Audit helper — thin wrapper so call sites stay readable
# ─────────────────────────────────────────────────────────────────────────────

def audit(action: str, detail: str = "", user_id: int = None) -> None:
    """Record an event in the audit_log table."""
    try:
        models.create_audit_entry(
            action=action,
            detail=detail,
            user_id=user_id,
            ip_address=_client_ip(),
        )
    except Exception as exc:
        # Never crash the request because of an audit failure
        logger.error("Audit log write failed: %s", exc)


def _client_ip() -> str:
    """
    Get the real client IP.
    ProxyFix (applied in __init__.py) rewrites REMOTE_ADDR when behind Nginx.
    """
    return request.remote_addr or "unknown"
