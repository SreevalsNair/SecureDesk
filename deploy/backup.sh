#!/usr/bin/env bash
# deploy/backup.sh
# Backup the SQLite database to AWS S3 using the EC2 instance IAM role.
# Uses sqlite3 .backup for a consistent hot backup (safe while app is running).
#
# Prerequisites:
#   - sqlite3 installed: sudo apt-get install -y sqlite3
#   - aws CLI installed: sudo apt-get install -y awscli
#   - IAM role with s3:PutObject permission on the backup bucket (see SECURITY_CHECKLIST.md)
#
# Usage:
#   sudo bash /var/www/securedesk/deploy/backup.sh
#
# Add to crontab (runs daily at 2:00 AM UTC):
#   0 2 * * * root /bin/bash /var/www/securedesk/deploy/backup.sh >> /var/www/securedesk/logs/backup.log 2>&1

set -euo pipefail

APP_DIR="/var/www/securedesk"
DB_PATH="$APP_DIR/securedesk.db"
BUCKET="s3://YOUR-BACKUP-BUCKET-NAME"    # <-- Replace with your S3 bucket name
TIMESTAMP=$(date +"%Y-%m-%dT%H-%M-%S")
BACKUP_FILE="/tmp/securedesk-backup-${TIMESTAMP}.db"

echo "[$(date -Iseconds)] Starting backup..."

# Security: sqlite3 .backup creates a consistent copy without locking the main DB
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

echo "  Snapshot created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# Upload to S3 using the instance IAM role (no credentials in this script)
aws s3 cp "$BACKUP_FILE" "${BUCKET}/db/${TIMESTAMP}.db" --sse AES256

echo "  Uploaded to ${BUCKET}/db/${TIMESTAMP}.db"

# Clean up local copy
rm -f "$BACKUP_FILE"
echo "[$(date -Iseconds)] Backup complete."

# Crontab line (add with: sudo crontab -e):
# 0 2 * * * root /bin/bash /var/www/securedesk/deploy/backup.sh >> /var/www/securedesk/logs/backup.log 2>&1
