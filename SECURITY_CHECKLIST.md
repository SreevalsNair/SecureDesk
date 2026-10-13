# SecureDesk — Security Checklist for Cloud Deployment

Work through this checklist **in order** before going live. Each item states what to do and why it matters.

---

## AWS Account & Access

- [ ] **SSH key-pair only login**
  - On EC2 launch: select "Create new key pair", download `.pem`
  - Disable password-based SSH: `sudo nano /etc/ssh/sshd_config` → `PasswordAuthentication no`
  - `sudo systemctl restart sshd`
  - **Threat stopped:** Attacker cannot brute-force your SSH login without the private key.

- [ ] **IAM role with least-privilege for backups**
  - In IAM → Roles → Create Role → EC2 use case
  - Attach this inline policy (replace `YOUR-BUCKET-NAME`):
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["s3:PutObject"],
        "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/db/*"
      }
    ]
  }
  ```
  - Attach the role to your EC2 instance (Instance → Actions → Security → Modify IAM Role)
  - **Threat stopped:** Even if the EC2 is compromised, the attacker can only write to that one S3 path — cannot read, delete, or access other AWS resources.

---

## Network Security

- [ ] **EC2 Security Group rules**
  - Inbound: 22/TCP from **your IP only** (not 0.0.0.0/0)
  - Inbound: 80/TCP from 0.0.0.0/0 (HTTP for Let's Encrypt challenge)
  - Inbound: 443/TCP from 0.0.0.0/0 (HTTPS for users)
  - All other inbound: DENY (default)
  - In EC2 Console → Security Groups → Edit inbound rules
  - **Threat stopped:** Reduces attack surface; nobody can reach internal ports (8000, 5432, etc.).

---

## HTTPS / TLS

- [ ] **Get a free domain (DuckDNS)**
  - Go to https://www.duckdns.org, sign in, create a subdomain (e.g. `securedesk.duckdns.org`)
  - Set the IP to your EC2 Elastic IP

- [ ] **Install Let's Encrypt certificate**
  ```bash
  sudo apt install -y certbot python3-certbot-nginx
  sudo certbot --nginx -d securedesk.duckdns.org
  # Follow prompts; Certbot auto-edits nginx.conf
  ```
  - Auto-renewal is configured automatically. Test with: `sudo certbot renew --dry-run`

- [ ] **Self-signed fallback (if no domain available)**
  ```bash
  sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/securedesk.key \
    -out /etc/ssl/certs/securedesk.crt \
    -subj "/CN=securedesk"
  ```
  Update nginx.conf to use these paths. Visitors will see a browser warning (acceptable for internal demo).

- [ ] **Enable secure cookies**
  - After HTTPS is working: edit `.env` → `SESSION_COOKIE_SECURE=true`
  - `sudo systemctl restart securedesk`
  - **Threat stopped:** Prevents cookie theft over HTTP (session hijacking).

---

## Storage

- [ ] **Encrypted EBS volume**
  - On EC2 launch: Storage → Encryption → Enable (uses AWS-managed KMS key)
  - For existing instance: create an encrypted snapshot and launch a new instance from it
  - **Threat stopped:** If AWS staff or someone with physical access removes the disk, the data is unreadable.

- [ ] **Encrypted S3 backup bucket with Block Public Access**
  - S3 → Create bucket → Block all public access ✓ (enabled by default)
  - Bucket → Properties → Default encryption → Enable (SSE-S3 or SSE-KMS)
  - `deploy/backup.sh` passes `--sse AES256` on upload
  - **Threat stopped:** Backup database cannot be accessed publicly or read without AWS credentials.

---

## Automated Backups

- [ ] **Enable daily backups via cron**
  ```bash
  # Edit backup.sh: set BUCKET=s3://YOUR-BUCKET-NAME
  sudo crontab -e
  # Add this line:
  0 2 * * * root /bin/bash /var/www/securedesk/deploy/backup.sh >> /var/www/securedesk/logs/backup.log 2>&1
  ```
  - Verify it ran: `sudo cat /var/www/securedesk/logs/backup.log`
  - **Threat stopped:** Ransomware or accidental deletion — you can restore from S3.

---

## Monitoring & Audit

- [ ] **Enable AWS CloudTrail**
  - AWS Console → CloudTrail → Create trail → All regions, S3 bucket for logs
  - **Threat stopped:** Records who called which AWS API and when — detects insider threats and unauthorized API access.

- [ ] **Set AWS Budget alert**
  - AWS Console → Billing → Budgets → Create budget
  - Monthly cost budget: \$10 (or your expected spend)
  - Email alert at 80% and 100%
  - **Threat stopped:** Detects crypto-mining or runaway resource usage caused by a compromised account.

- [ ] **Review application audit log regularly**
  - Log in as admin → Audit Log
  - Look for: many `login_failure` entries (brute force), `access_denied` entries (probing), unexpected `lockout` events
  - **Threat stopped:** Early detection of ongoing attacks.

---

## Application Hardening Verification

- [ ] **Confirm `DEBUG=False` in production**
  - `sudo grep -r "DEBUG" /var/www/securedesk/.env` → should not appear, or be False
  - **Threat stopped:** Flask debug mode exposes an interactive shell to anyone who triggers an error.

- [ ] **Confirm `SECRET_KEY` is not the placeholder**
  - `sudo grep SECRET_KEY /var/www/securedesk/.env`
  - Must not be `dev-insecure-placeholder-change-me`
  - **Threat stopped:** Predictable secret key allows session forgery.

- [ ] **Check security headers are present**
  ```bash
  curl -si http://localhost | grep -E "Content-Security|X-Frame|X-Content"
  ```
  - Should see: `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`
  - **Threat stopped:** XSS, clickjacking, MIME sniffing attacks.
