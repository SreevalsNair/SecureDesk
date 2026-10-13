"""
app/models.py
Data-access layer for SecureDesk.
All SQL lives here — nowhere else in the application.
Every query is parameterized via db.query_db / db.execute_db.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from app.db import query_db, execute_db


# ─────────────────────────────────────────────────────────────────────────────
# User model helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    return query_db(
        "SELECT * FROM users WHERE id = ?", (user_id,), one=True
    )


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    return query_db(
        "SELECT * FROM users WHERE email = ?", (email,), one=True
    )


def create_user(name: str, email: str, password_hash: str, role: str = "student") -> int:
    """Insert a new user; return the new row's id."""
    return execute_db(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (name, email, password_hash, role),
    )


def increment_failed_attempts(user_id: int) -> None:
    execute_db(
        "UPDATE users SET failed_attempts = failed_attempts + 1 WHERE id = ?",
        (user_id,),
    )


def set_lockout(user_id: int, locked_until_iso: str) -> None:
    """Lock account until the given ISO-8601 timestamp."""
    execute_db(
        "UPDATE users SET locked_until = ? WHERE id = ?",
        (locked_until_iso, user_id),
    )


def reset_failed_attempts(user_id: int) -> None:
    """Clear lockout state on successful login."""
    execute_db(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (user_id,),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Complaint model helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_complaint(user_id: int, title: str, category: str, description: str) -> int:
    return execute_db(
        """INSERT INTO complaints (user_id, title, category, description)
           VALUES (?, ?, ?, ?)""",
        (user_id, title, category, description),
    )


def get_complaints_by_user(user_id: int) -> list:
    """Security: IDOR protection — filters by user_id so a student cannot read another's data."""
    return query_db(
        """SELECT c.*, u.name AS student_name
           FROM complaints c JOIN users u ON c.user_id = u.id
           WHERE c.user_id = ?
           ORDER BY c.created_at DESC""",
        (user_id,),
    )


def get_all_complaints(status: str = None, category: str = None) -> list:
    """Admin view — optional filter by status and/or category."""
    base = """
        SELECT c.*, u.name AS student_name
        FROM complaints c JOIN users u ON c.user_id = u.id
        WHERE 1=1
    """
    args: list = []
    if status:
        base += " AND c.status = ?"
        args.append(status)
    if category:
        base += " AND c.category = ?"
        args.append(category)
    base += " ORDER BY c.created_at DESC"
    return query_db(base, tuple(args))


def get_complaint_by_id(complaint_id: int) -> Optional[sqlite3.Row]:
    return query_db(
        "SELECT * FROM complaints WHERE id = ?", (complaint_id,), one=True
    )


def update_complaint_status(complaint_id: int, new_status: str) -> None:
    execute_db(
        """UPDATE complaints
           SET status = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (new_status, complaint_id),
    )


def get_complaint_stats() -> dict:
    """Return counts by status for the admin dashboard tiles."""
    rows = query_db(
        """SELECT status, COUNT(*) AS cnt FROM complaints GROUP BY status"""
    )
    stats = {"total": 0, "Pending": 0, "In Progress": 0, "Resolved": 0}
    for row in rows:
        stats[row["status"]] = row["cnt"]
        stats["total"] += row["cnt"]
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Audit log helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_audit_entry(
    action: str,
    detail: str = "",
    user_id: int = None,
    ip_address: str = None,
) -> None:
    """Insert a row into audit_log. user_id is nullable (pre-auth events)."""
    execute_db(
        """INSERT INTO audit_log (user_id, action, detail, ip_address)
           VALUES (?, ?, ?, ?)""",
        (user_id, action, detail, ip_address),
    )


def get_audit_log(page: int = 1, per_page: int = 20) -> tuple[list, int]:
    """Return (rows, total_count) for a paginated, newest-first audit view."""
    offset = (page - 1) * per_page
    total_row = query_db("SELECT COUNT(*) AS cnt FROM audit_log", one=True)
    total = total_row["cnt"] if total_row else 0
    rows = query_db(
        """SELECT a.*, u.name AS user_name, u.email AS user_email
           FROM audit_log a LEFT JOIN users u ON a.user_id = u.id
           ORDER BY a.timestamp DESC
           LIMIT ? OFFSET ?""",
        (per_page, offset),
    )
    return rows, total
