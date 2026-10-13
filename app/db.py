"""
app/db.py
Database connection handling for SecureDesk.
- Single function to get a per-request connection stored in Flask's g object.
- Enables WAL mode and foreign-key enforcement on every connection.
- init_db() reads and executes schema.sql.
- All queries MUST be parameterized — never format SQL strings with user input.
"""

import os
import sqlite3
import logging

from flask import g, current_app

logger = logging.getLogger(__name__)


def get_db() -> sqlite3.Connection:
    """
    Return the SQLite connection for the current request context.
    Creates one if it does not exist yet (stored in Flask's g).
    """
    if "db" not in g:
        db_path = current_app.config["DB_PATH"]

        # In testing with :memory:, store connection on app._test_db to persist across contexts
        if db_path == ":memory:" and hasattr(current_app, "_test_db") and current_app._test_db is not None:
            g.db = current_app._test_db
            return g.db

        # Create the parent directory if it does not exist
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        try:
            conn = sqlite3.connect(
                db_path,
                detect_types=sqlite3.PARSE_DECLTYPES,
                timeout=10,
            )
            conn.row_factory = sqlite3.Row   # Access columns by name

            # Security: enforce referential integrity (SQLite ignores FK by default)
            conn.execute("PRAGMA foreign_keys = ON")

            # Performance: WAL mode allows concurrent reads during a write (not for :memory:)
            if db_path != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL")

            if db_path == ":memory:":
                current_app._test_db = conn

            g.db = conn
        except sqlite3.OperationalError as exc:
            logger.error("Database connection failed: %s", exc)
            raise  # Caught by the 500 error handler in __init__.py

    return g.db


def close_db(exc=None) -> None:
    """Teardown function — close the connection at end of request."""
    db = g.pop("db", None)
    if db is not None:
        if current_app.config.get("DB_PATH") != ":memory:":
            db.close()


def init_db(app) -> None:
    """
    Create all tables by executing schema.sql.
    Called by manage.py init-db; safe to run multiple times (IF NOT EXISTS).
    """
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schema.sql")
    with app.app_context():
        db = get_db()
        with open(schema_path, "r") as f:
            db.executescript(f.read())
        db.commit()
        logger.info("Database initialised at %s", app.config["DB_PATH"])


def query_db(query: str, args: tuple = (), one: bool = False):
    """
    Execute a SELECT query and return Row objects.
    :param query: Parameterized SQL string (use ? placeholders).
    :param args:  Tuple of bind parameters — prevents SQL injection.
    :param one:   If True, return a single Row or None instead of a list.
    """
    cur = get_db().execute(query, args)   # Parameterized — Security: SQL injection prevention
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query: str, args: tuple = ()) -> int:
    """
    Execute an INSERT/UPDATE/DELETE query.
    Returns lastrowid for INSERT, else 0.
    Commits automatically.
    """
    db = get_db()
    cur = db.execute(query, args)          # Parameterized — Security: SQL injection prevention
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id
