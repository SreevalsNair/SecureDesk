"""
wsgi.py
Gunicorn entry point for SecureDesk.

Usage:
  gunicorn --workers 2 --bind 0.0.0.0:8000 wsgi:app

Note on Flask-Limiter with multiple workers:
  The in-memory rate-limit store is per-process, so each of the 2 workers
  tracks limits independently. This means the effective global limit is
  2x the configured value in the worst case.
  The authoritative brute-force control is the DB-based account lockout
  (5 failed attempts -> 15-minute ban), which is shared across all workers.
  See README.md for the mitigation strategy.
"""

import os
from dotenv import load_dotenv

# Load .env before creating the app so all env vars are present
load_dotenv()

from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "production"))

if __name__ == "__main__":
    # Direct run for quick testing only — use gunicorn in production
    app.run()
