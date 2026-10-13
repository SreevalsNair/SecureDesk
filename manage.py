"""
manage.py
CLI management commands for SecureDesk.
Usage:
  python manage.py init-db          — Create all tables from schema.sql
  python manage.py create-admin     — Create the admin account from env vars
  python manage.py seed-demo        — Insert demo users and complaints for testing
"""

import os
import secrets
import string
import sys

# Load .env before anything else so env vars are available to config
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.db import init_db, get_db
from app.models import create_user, get_user_by_email
from app.security import hash_password


def _make_app(env: str = "development"):
    return create_app(env)


def cmd_init_db():
    """Create all database tables using schema.sql."""
    app = _make_app()
    init_db(app)
    print("[OK] Database initialised:", app.config["DB_PATH"])


def cmd_create_admin():
    """
    Create the admin account.
    Reads ADMIN_EMAIL and ADMIN_PASSWORD from environment / .env file.
    Security: password is never stored in source code.
    """
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()

    if not email:
        print("[ERROR] ADMIN_EMAIL is not set. Add it to your .env file.")
        sys.exit(1)
    if not password:
        print("[ERROR] ADMIN_PASSWORD is not set. Add it to your .env file.")
        sys.exit(1)

    # Validate password strength
    from app.validators import validate_password
    err = validate_password(password)
    if err:
        print(f"[ERROR] ADMIN_PASSWORD is too weak: {err}")
        sys.exit(1)

    app = _make_app()
    with app.app_context():
        existing = get_user_by_email(email.lower())
        if existing:
            print(f"[!] Admin account already exists: {email}")
        else:
            pw_hash = hash_password(password)
            create_user(name="Admin", email=email.lower(), password_hash=pw_hash, role="admin")
            print(f"[OK] Admin account created: {email}")


def cmd_seed_demo():
    """
    Insert a handful of demo users and complaints for viva demonstrations.
    Generates random passwords, prints them once, never stores them in code.
    Security: passwords are random and shown only at seed time.
    """
    from app.validators import validate_password

    def _random_password():
        """Generate a random 12-character password meeting the complexity rule."""
        alphabet = string.ascii_letters + string.digits
        while True:
            pwd = "".join(secrets.choice(alphabet) for _ in range(12))
            if validate_password(pwd) is None:
                return pwd

    demo_users = [
        {"name": "Alice Student",   "email": "alice@demo.example"},
        {"name": "Bob Classmate",   "email": "bob@demo.example"},
        {"name": "Carol Freshman",  "email": "carol@demo.example"},
    ]

    demo_complaints = [
        {"title": "WiFi not working in Room 204",  "category": "Hostel",    "description": "The WiFi router on the second floor has been down for three days."},
        {"title": "Lab computers crashing",         "category": "Lab",       "description": "All PCs in Lab 3 crash when running Python scripts."},
        {"title": "Exam schedule not published",    "category": "Academic",  "description": "End-of-semester exam timetable has not been released yet."},
        {"title": "Ragging in canteen",             "category": "Harassment","description": "Senior students are bullying juniors during lunch. Please investigate."},
        {"title": "Library closes too early",       "category": "Other",     "description": "Library closes at 6 PM but students need access until 9 PM."},
    ]

    app = _make_app()
    with app.app_context():
        created_users = []
        for u in demo_users:
            existing = get_user_by_email(u["email"])
            if existing:
                print(f"  [skip] {u['email']} already exists")
                created_users.append(existing["id"])
            else:
                pwd = _random_password()
                pw_hash = hash_password(pwd)
                uid = create_user(u["name"], u["email"], pw_hash, role="student")
                created_users.append(uid)
                # Print once — never stored in code or DB
                print(f"  [OK] Created user: {u['email']}  password: {pwd}")

        db = get_db()
        for i, c in enumerate(demo_complaints):
            uid = created_users[i % len(created_users)]
            db.execute(
                "INSERT INTO complaints (user_id, title, category, description) VALUES (?, ?, ?, ?)",
                (uid, c["title"], c["category"], c["description"]),
            )
        db.commit()
        print(f"[OK] {len(demo_complaints)} demo complaints created.")
        print("[!] Passwords printed above are shown ONLY once — save them now.")


COMMANDS = {
    "init-db":      cmd_init_db,
    "create-admin": cmd_create_admin,
    "seed-demo":    cmd_seed_demo,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python manage.py <command>")
        print("Commands:", ", ".join(COMMANDS.keys()))
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
