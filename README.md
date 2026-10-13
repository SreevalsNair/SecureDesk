# SecureDesk

**A lightweight, secure college complaint management system built with Flask and SQLite.**

This is a Cloud Computing mini-project demonstrating secure web application development, AWS EC2 deployment, and cloud-native best practices.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9–3.12, Flask 3.0 |
| Database | SQLite (standard library sqlite3, WAL mode) |
| Auth | Flask-Login, bcrypt |
| CSRF | Flask-WTF |
| Rate limiting | Flask-Limiter |
| Frontend | Jinja2 templates, vanilla JS, plain CSS |
| Server | Gunicorn 2 workers behind Nginx |
| Cloud | AWS EC2 t4g.micro (ARM64), S3 (backups), IAM |

---

## Folder Map

```
securedesk/
├── app/
│   ├── __init__.py          # App factory, extensions, security headers, error handlers
│   ├── config.py            # Dev / Production / Testing config classes
│   ├── db.py                # SQLite connection, WAL mode, FK enforcement
│   ├── models.py            # All SQL queries (parameterized)
│   ├── security.py          # bcrypt, lockout logic, role_required decorator, audit helper
│   ├── validators.py        # Server-side field validation, state-machine transitions
│   ├── blueprints/
│   │   ├── main.py          # / redirect, /health
│   │   ├── auth.py          # /auth/register, /auth/login, /auth/logout
│   │   ├── complaints.py    # /complaints/dashboard, /complaints/new
│   │   ├── admin.py         # /admin/dashboard, /admin/audit
│   │   └── api.py           # /api/complaints, /api/complaints/<id>/status
│   ├── templates/           # Jinja2 HTML templates
│   └── static/
│       ├── css/style.css    # All CSS (no external assets)
│       ├── js/live.js       # 5-second polling, live table updates
│       └── js/admin.js      # CSRF-header fetch for status updates
├── schema.sql               # DB schema (users, complaints, audit_log)
├── manage.py                # CLI: init-db, create-admin, seed-demo
├── wsgi.py                  # Gunicorn entry point
├── tests/
│   └── test_security.py     # Security-focused pytest suite
├── deploy/
│   ├── nginx.conf           # Reverse proxy config
│   ├── securedesk.service   # Systemd unit (non-root user)
│   ├── setup.sh             # Idempotent EC2 setup script
│   └── backup.sh            # SQLite -> S3 backup
├── requirements.txt         # Pinned production deps
├── requirements-dev.txt     # + pytest
├── .env.example             # Template for secrets
└── .gitignore
```

---

## Local Setup

### Prerequisites
- Python 3.9+ installed
- Git

### Windows (PowerShell)

```powershell
# 1. Clone / enter project
cd "Cloud CA3"

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements-dev.txt

# 4. Create .env
copy .env.example .env
# Edit .env: set SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD

# 5. Set FLASK_ENV for development
$env:FLASK_ENV = "development"

# 6. Initialise database
python manage.py init-db

# 7. Create admin account
python manage.py create-admin

# 8. (Optional) Load demo data
python manage.py seed-demo

# 9. Run development server
flask --app wsgi run --debug
# Visit http://127.0.0.1:5000
```

### Linux / macOS

```bash
# 1. Create and activate venv
python3 -m venv venv
source venv/bin/activate

# 2. Install deps
pip install -r requirements-dev.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your values

# 4. Init database + admin
python manage.py init-db
python manage.py create-admin

# 5. Run
export FLASK_ENV=development
flask --app wsgi run --debug
```

---

## Running Tests

```bash
# Activate venv first
pip install -r requirements-dev.txt

pytest tests/ -v
```

Tests run against an in-memory SQLite DB — no side effects on your real database.

---

## Listing All Routes

```bash
flask --app wsgi routes
```

---

## EC2 Server Deployment (for your teammate)

### Step 1 — Launch an EC2 instance
- AMI: Ubuntu 22.04 LTS (ARM64)
- Instance type: t4g.micro (free tier eligible)
- Security Group: allow port 22 (your IP only), 80, 443

### Step 2 — SSH in and clone the repo
```bash
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
git clone https://github.com/yourrepo/securedesk.git /var/www/securedesk
cd /var/www/securedesk
```

### Step 3 — Run the setup script
```bash
sudo bash deploy/setup.sh
```
This script:
- Creates a 1 GB swap file (needed on 1 GB RAM instance)
- Installs Python, Nginx, Git
- Creates a `securedesk` non-root user
- Creates a venv and installs requirements
- Generates a random SECRET_KEY in `.env`
- Initialises the database
- Installs and starts the Nginx + Gunicorn systemd service

### Step 4 — Set secrets
```bash
sudo nano /var/www/securedesk/.env
# Set: ADMIN_EMAIL, ADMIN_PASSWORD, SESSION_COOKIE_SECURE=true (after HTTPS)
```

### Step 5 — Create admin account
```bash
sudo -u securedesk /var/www/securedesk/venv/bin/python /var/www/securedesk/manage.py create-admin
```

### Step 6 — (Optional) HTTPS with Let's Encrypt
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.duckdns.org
# Then set SESSION_COOKIE_SECURE=true in .env and restart:
sudo systemctl restart securedesk
```

### Step 7 — Set up automated backups
```bash
# Edit backup.sh: replace YOUR-BACKUP-BUCKET-NAME
sudo crontab -e
# Add: 0 2 * * * root /bin/bash /var/www/securedesk/deploy/backup.sh >> /var/www/securedesk/logs/backup.log 2>&1
```

### Checking service status
```bash
sudo systemctl status securedesk
sudo journalctl -u securedesk -f      # Live logs
tail -f /var/www/securedesk/logs/securedesk.log
```

---

## Note on Rate Limiting with 2 Gunicorn Workers

Flask-Limiter uses an in-memory store (one per worker process). With 2 workers, a client could theoretically make 2× the configured limit before being blocked at the rate-limit level. **This is acceptable because:**

1. The authoritative brute-force control is **DB-based account lockout** (5 failed attempts → 15-minute ban), which is shared across all workers via the database.
2. Rate limiting is an additional layer, not the only one.
3. For production with strict per-IP limiting, replace `RATELIMIT_STORAGE_URI = "memory://"` with a Redis URI.
