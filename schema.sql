-- SecureDesk Database Schema
-- Enable foreign key enforcement and WAL mode at connection time (done in db.py)

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'student' CHECK(role IN ('student','admin')),
    failed_attempts INTEGER NOT NULL DEFAULT 0,          -- Security: account lockout
    locked_until  TEXT,                                  -- ISO-8601 timestamp or NULL
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS complaints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    category    TEXT    NOT NULL CHECK(category IN ('Hostel','Lab','Academic','Harassment','Other')),
    description TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','In Progress','Resolved')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- nullable: pre-auth events
    action     TEXT    NOT NULL,
    detail     TEXT,
    ip_address TEXT,
    timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_complaints_user   ON complaints(user_id);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp   ON audit_log(timestamp DESC);
