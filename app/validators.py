"""
app/validators.py
Server-side input validation for SecureDesk.
Client-side checks are UX only — the server ALWAYS re-validates.
Security: prevents malformed data reaching the database layer.
"""

from __future__ import annotations

import re
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

VALID_CATEGORIES = {"Hostel", "Lab", "Academic", "Harassment", "Other"}
VALID_STATUSES = {"Pending", "In Progress", "Resolved"}

# Allowed status transitions — Security: prevents invalid/skipped state changes
ALLOWED_TRANSITIONS = {
    "Pending": {"In Progress"},
    "In Progress": {"Resolved"},
    "Resolved": set(),          # Terminal state
}

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

MIN_PASSWORD_LEN = 8
MAX_NAME_LEN = 100
MAX_EMAIL_LEN = 254
MAX_TITLE_LEN = 200
MAX_DESC_LEN = 2000


# ─────────────────────────────────────────────────────────────────────────────
# Field validators — return None on success, error string on failure
# ─────────────────────────────────────────────────────────────────────────────

def validate_name(name: str) -> Optional[str]:
    name = name.strip()
    if not name:
        return "Name is required."
    if len(name) > MAX_NAME_LEN:
        return f"Name must be {MAX_NAME_LEN} characters or fewer."
    return None


def validate_email(email: str) -> Optional[str]:
    email = email.strip()
    if not email:
        return "Email is required."
    if len(email) > MAX_EMAIL_LEN:
        return "Email address is too long."
    if not EMAIL_RE.match(email):
        return "Enter a valid email address."
    return None


def validate_password(password: str) -> Optional[str]:
    """
    Security: enforce minimum complexity so bcrypt protects a reasonably strong secret.
    """
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    if not re.search(r"[A-Za-z]", password):
        return "Password must contain at least one letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one digit."
    return None


def validate_complaint_title(title: str) -> Optional[str]:
    title = title.strip()
    if not title:
        return "Title is required."
    if len(title) > MAX_TITLE_LEN:
        return f"Title must be {MAX_TITLE_LEN} characters or fewer."
    return None


def validate_complaint_description(desc: str) -> Optional[str]:
    desc = desc.strip()
    if not desc:
        return "Description is required."
    if len(desc) > MAX_DESC_LEN:
        return f"Description must be {MAX_DESC_LEN} characters or fewer."
    return None


def validate_category(category: str) -> Optional[str]:
    """Security: whitelist check — rejects any value not in the allowed set."""
    if category not in VALID_CATEGORIES:
        return f"Category must be one of: {', '.join(sorted(VALID_CATEGORIES))}."
    return None


def validate_status_transition(current_status: str, new_status: str) -> Optional[str]:
    """
    Security: enforce allowed state machine transitions server-side.
    Prevents an attacker from jumping straight to Resolved, or re-opening complaints.
    """
    if new_status not in VALID_STATUSES:
        return f"Invalid status value: {new_status}."
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        return (
            f"Cannot change status from '{current_status}' to '{new_status}'. "
            f"Allowed next states: {', '.join(allowed) or 'none (terminal)'}."
        )
    return None


def validate_safe_redirect(url: str, allowed_hosts: set = None) -> bool:
    """
    Security: open-redirect prevention.
    Only allow relative URLs (no scheme, no netloc).
    """
    if not url:
        return False
    # A safe redirect starts with / but not //
    return url.startswith("/") and not url.startswith("//")
