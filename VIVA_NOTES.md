# SecureDesk — Viva Notes

---

## (a) Threat-to-Control Table

| Threat | Description | Control in SecureDesk | File / AWS Setting |
|--------|------------|----------------------|-------------------|
| **SQL Injection** | Attacker injects SQL in form fields to read/modify DB | All queries use `?` parameterized placeholders; user input never interpolated into SQL | `app/db.py` → `query_db()`, `execute_db()`; `app/models.py` all functions |
| **XSS (Cross-Site Scripting)** | Attacker stores `<script>` in complaint; victim browser runs it | Jinja2 autoescaping ON by default (never `|safe`); JS uses `textContent` not `innerHTML` | `app/templates/*.html`; `app/static/js/live.js`, `admin.js` |
| **CSRF** | Forged request tricks logged-in user into performing actions | Flask-WTF CSRF token on every form; `X-CSRFToken` header required on fetch POSTs; token in `<meta>` tag | `app/__init__.py` (CSRFProtect), all form templates, `admin.js` |
| **Brute Force / Credential Stuffing** | Automated password guessing on login | (1) DB lockout: 5 failures → 15-min ban; (2) Flask-Limiter: 10 req/min on login/register; (3) Generic error message (no user enumeration) | `app/security.py` → `handle_failed_login()`, `is_account_locked()`; `app/blueprints/auth.py` |
| **Privilege Escalation / IDOR** | Student accesses admin routes or another student's data | `@role_required("admin")` decorator returns 403 for wrong role; complaint queries always filter by `user_id = current_user.id` | `app/security.py` → `role_required()`; `app/models.py` → `get_complaints_by_user()` |
| **Password Theft** | Attacker reads DB file and gets plaintext passwords | Passwords hashed with bcrypt (work factor 12); minimum 8 chars, 1 letter + 1 digit required | `app/security.py` → `hash_password()`, `verify_password()`; `app/validators.py` |
| **Eavesdropping (MITM)** | Attacker sniffs HTTP traffic to steal session cookies | HTTPS (TLS 1.2/1.3 via Nginx + Certbot); HSTS header; `SESSION_COOKIE_SECURE=true`; `HttpOnly` cookie | `deploy/nginx.conf`; `app/__init__.py` HSTS header; `app/config.py` cookie settings |
| **Data Loss** | Hardware failure, ransomware, or accidental deletion | Daily `sqlite3 .backup` to S3 with server-side encryption; encrypted EBS volume | `deploy/backup.sh`; AWS S3 SSE; AWS EBS encryption |
| **Unauthorized AWS Access** | Compromised AWS keys; overprivileged IAM | IAM role with `s3:PutObject` only on backup bucket (least privilege); no long-term credentials on EC2; CloudTrail audit; Budget alert | AWS IAM policy in `SECURITY_CHECKLIST.md`; CloudTrail; AWS Budgets |

---

## (b) Live Demo Script

### Setup commands (run before examiner arrives)
```bash
# Start the server
flask --app wsgi run

# Open a second terminal for sqlite3 inspection
sqlite3 securedesk.db
```

---

### Step 1 — Student registers and submits a complaint

1. Open http://127.0.0.1:5000 in browser
2. Click **Register** → enter name, email, password (e.g. `alice@test.com` / `Alice1234`)
3. Log in as alice
4. Click **New Complaint** → fill in:
   - Title: `WiFi down in Room 204`
   - Category: `Hostel`
   - Description: `The router on floor 2 has been down since Monday.`
5. Submit → dashboard shows complaint with status **Pending**

**Show the row via sqlite3:**
```sql
-- In your second terminal:
sqlite3 securedesk.db
SELECT id, title, status, created_at FROM complaints ORDER BY id DESC LIMIT 1;
SELECT action, detail, ip_address, timestamp FROM audit_log ORDER BY id DESC LIMIT 3;
.quit
```

---

### Step 2 — Admin changes status

1. Open a new browser tab (or incognito)
2. Log in as admin
3. Admin dashboard shows the complaint
4. Click **Mark In Progress** → row updates **without page reload**
5. Go back to student tab → within 5 seconds, the badge changes to **In Progress** (live polling)

**Show the state change in sqlite3:**
```sql
SELECT id, status, updated_at FROM complaints WHERE id = 1;
SELECT action, detail FROM audit_log WHERE action = 'status_changed' ORDER BY id DESC LIMIT 1;
```

---

### Step 3 — Show audit log

- Admin → Audit Log page
- Point out: login events, complaint_created, status_changed, timestamps, IP addresses

---

### Step 4 — SQL injection attempt

In the login form, enter:
- Email: `' OR '1'='1' --`
- Password: `anything`

**Expected result:** "Invalid email or password." error — no bypass, no crash.

**Explain:** The query is `WHERE email = ?` with a parameterized placeholder. The `'` is treated as data, not SQL syntax.

**sqlite3 evidence:**
```sql
SELECT * FROM users;  -- Shows only real registered users, no injection data
SELECT action, detail FROM audit_log WHERE action='login_failure' ORDER BY id DESC LIMIT 2;
```

---

### Step 5 — XSS attempt

Log in as alice. Submit a new complaint with:
- Title: `<script>alert('XSS')</script>`
- Category: `Other`
- Description: `Testing XSS`

**Expected result:** No alert box. The title appears as literal text `<script>alert('XSS')</script>` in the table.

**Explain two layers of protection:**
1. Jinja2 autoescaping: `{{ c.title }}` renders as `&lt;script&gt;...` in HTML
2. JS live updates use `element.textContent = c.title` (not `innerHTML`), so even the raw string is safe

---

### Step 6 — Brute force / lockout demo

1. Log out
2. Try to log in with alice's email and wrong password **5 times**
3. On the 5th attempt: still shows "Invalid email or password."
4. Try with the **correct** password → still locked!

**sqlite3 evidence:**
```sql
SELECT email, failed_attempts, locked_until FROM users WHERE email='alice@test.com';
SELECT action, detail FROM audit_log WHERE action IN ('login_failure','lockout') ORDER BY id DESC LIMIT 6;
```

Wait 15 minutes (or for demo: temporarily update `locked_until` to the past):
```sql
UPDATE users SET locked_until=NULL, failed_attempts=0 WHERE email='alice@test.com';
```

---

## (c) 15 Likely Viva Questions & Short Answers

**Q1. Why did you use SQLite instead of PostgreSQL or MySQL?**
SQLite requires no separate server process, making it ideal for a single EC2 instance with limited RAM. The standard library `sqlite3` module means zero extra dependencies. WAL mode gives us concurrent reads while a write is happening.

**Q2. What is SQL injection and how does SecureDesk prevent it?**
SQL injection is when an attacker puts SQL code inside a form field (e.g. `' OR '1'='1'`) to manipulate the query. We prevent it by using parameterized queries (`?` placeholders) in every `db.execute()` call. The database driver sends the SQL and data separately, so the data can never be interpreted as SQL syntax.

**Q3. What is XSS and where do you handle it?**
XSS (Cross-Site Scripting) is when an attacker stores a `<script>` tag in user input and it runs in another user's browser. We have two defences: (1) Jinja2 autoescaping converts `<` to `&lt;` before putting any variable into HTML; (2) our JavaScript always uses `element.textContent`, never `element.innerHTML`, when setting user-supplied data. The Content-Security-Policy header (`script-src 'self'`) blocks any inline scripts too.

**Q4. What is CSRF and how does Flask-WTF prevent it?**
CSRF (Cross-Site Request Forgery) tricks a logged-in user's browser into making a request to our site from a malicious page. Flask-WTF generates a unique token per session. Every form includes this token as a hidden field. Every fetch POST reads it from a `<meta>` tag and sends it as `X-CSRFToken`. The server rejects any request without a valid token.

**Q5. How does account lockout work?**
The `users` table has `failed_attempts` and `locked_until` columns. On every wrong password, `failed_attempts` is incremented. When it reaches 5, `locked_until` is set to `now() + 15 minutes`. Every login attempt first checks if `locked_until` is in the future — if yes, it rejects with the same generic message, regardless of whether the password was correct.

**Q6. Why do you show the same error message for wrong password and unknown email?**
If we showed "Email not found" for unknown emails and "Wrong password" for known ones, an attacker could enumerate valid accounts by trying random emails. The generic message "Invalid email or password" prevents this.

**Q7. What is bcrypt and why is work factor 12 used?**
bcrypt is a password-hashing algorithm designed to be slow. Work factor 12 means it runs 2¹² = 4096 rounds of an internal key schedule, taking ~200ms per hash. This makes offline brute-force attacks impractically slow — an attacker who steals the DB cannot crack passwords quickly.

**Q8. What is the role_required decorator and what does it prevent?**
`@role_required("admin")` checks that the current user's role matches before executing the view function. If not, it returns HTTP 403 and logs an audit entry. This prevents privilege escalation: a student who somehow gets a URL to `/admin/dashboard` gets denied.

**Q9. What is IDOR and how is it handled?**
IDOR (Insecure Direct Object Reference) is when a user can access another user's data by changing an ID in the URL. In `models.py`, the query for student complaints is `WHERE user_id = ?` with `current_user.id` — even if a student guesses complaint ID 1, they can only get it if it belongs to them. The database does the ownership check.

**Q10. Why is the SESSION_COOKIE_SECURE flag important?**
When set to True, the browser only sends the session cookie over HTTPS connections, never HTTP. This prevents an attacker on the same network from stealing the cookie by intercepting HTTP traffic (session hijacking).

**Q11. What does ProxyFix do?**
When Nginx forwards requests to Gunicorn, `REMOTE_ADDR` becomes `127.0.0.1` (the Nginx proxy). ProxyFix reads the `X-Forwarded-For` header that Nginx sets and replaces `REMOTE_ADDR` with the real client IP. This is needed for correct rate limiting and audit logging.

**Q12. Why use a rotating log file and what is never logged?**
A `RotatingFileHandler` caps the log file at 5 MB and keeps 5 backups — preventing the disk from filling up. We never log passwords, session tokens, or secret keys, which would create a secondary attack surface if the log file were stolen.

**Q13. What security headers does the app send on every response?**
- `Content-Security-Policy: default-src 'self'` — only scripts/styles from our own domain run
- `X-Frame-Options: DENY` — prevents clickjacking in iframes
- `X-Content-Type-Options: nosniff` — browser won't guess file types
- `Referrer-Policy` — limits URL leakage in Referer headers
- `Strict-Transport-Security` — forces HTTPS for one year (when HTTPS is on)

**Q14. What is the limitation of Flask-Limiter with 2 Gunicorn workers?**
Each worker has its own in-memory rate-limit counter. If an attacker's requests are load-balanced between workers, they could make up to 2× the limit before being blocked. The authoritative control is the DB-based account lockout, which is shared across all workers. In production, this can be solved by using a Redis backend for Flask-Limiter.

**Q15. How would you scale this application if it needed to serve 10,000 users?**
(1) Replace SQLite with PostgreSQL (add connection pooling via psycopg2/SQLAlchemy). (2) Move to Redis for session storage and rate-limit counters. (3) Put the app behind an Application Load Balancer with multiple EC2 instances or use ECS/Fargate containers. (4) Use RDS for managed database with Multi-AZ replication. (5) Add CloudFront CDN for static assets. (6) Use AWS WAF for network-level rate limiting and OWASP rule sets.
