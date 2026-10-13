"""
query_db.py — Easy CLI query tool for SecureDesk in PowerShell/Bash
Usage:
    python query_db.py complaints
    python query_db.py users
    python query_db.py audit
"""
import sys
import sqlite3

def run(query, headers):
    conn = sqlite3.connect("securedesk.db")
    cur = conn.cursor()
    rows = cur.execute(query).fetchall()
    conn.close()

    if not rows:
        print("[Empty result]")
        return

    # Print table header
    col_widths = [max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))]
    header_line = " | ".join(f"{headers[i]:<{col_widths[i]}}" for i in range(len(headers)))
    print(header_line)
    print("-" * len(header_line))

    # Print rows
    for r in rows:
        print(" | ".join(f"{str(r[i]):<{col_widths[i]}}" for i in range(len(r))))

def show_complaints():
    print("\n=== LATEST COMPLAINTS ===")
    q = "SELECT id, title, category, status, datetime(updated_at, 'localtime') FROM complaints ORDER BY id DESC LIMIT 5"
    run(q, ["ID", "TITLE", "CATEGORY", "STATUS", "UPDATED (LOCAL)"])

def show_users():
    print("\n=== USERS & LOCKOUT STATUS ===")
    q = "SELECT id, name, email, role, failed_attempts, locked_until FROM users"
    run(q, ["ID", "NAME", "EMAIL", "ROLE", "FAILED ATTEMPTS", "LOCKED UNTIL"])

def show_audit():
    print("\n=== LATEST AUDIT EVENTS ===")
    q = "SELECT id, action, detail, ip_address, datetime(timestamp, 'localtime') FROM audit_log ORDER BY id DESC LIMIT 5"
    run(q, ["ID", "ACTION", "DETAIL", "IP", "TIMESTAMP (LOCAL)"])

if __name__ == "__main__":
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if arg in ("complaints", "c"):
        show_complaints()
    elif arg in ("users", "u"):
        show_users()
    elif arg in ("audit", "a"):
        show_audit()
    else:
        show_complaints()
        show_users()
        show_audit()
