"""
watch_db.py — Live database monitor for SecureDesk
Displays complaints and audit events, refreshing every 1 second.
"""
import os
import sys
import time
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "securedesk.db")

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database file not found at: {os.path.abspath(DB_PATH)}")
        print("Please run: python manage.py init-db first.")
        sys.exit(1)

    print("Starting SecureDesk Live Database Monitor...")
    time.sleep(1)

    while True:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.row_factory = sqlite3.Row

            cur = conn.cursor()
            cur.execute("""
                SELECT id, title, category, status, datetime(updated_at, 'localtime') AS updated_at 
                FROM complaints 
                ORDER BY id DESC 
                LIMIT 8
            """)
            complaints = cur.fetchall()

            cur.execute("""
                SELECT action, detail, datetime(timestamp, 'localtime') AS timestamp 
                FROM audit_log 
                ORDER BY id DESC 
                LIMIT 4
            """)
            audits = cur.fetchall()
            conn.close()

            clear_screen()
            now = time.strftime("%H:%M:%S")
            print("=" * 76)
            print(f"  SECUREDESK LIVE DATABASE MONITOR  |  Local Time: {now} (updates every 1s)")
            print(f"  Target DB: {os.path.abspath(DB_PATH)}")
            print("=" * 76)
            print("\n--- [LATEST COMPLAINTS] ---")
            print(f"{'ID':<4} | {'STATUS':<13} | {'CATEGORY':<12} | {'TITLE':<25} | {'LAST UPDATED'}")
            print("-" * 76)

            for c in complaints:
                status_display = c['status'].upper()
                title_short = (c['title'][:22] + "...") if len(c['title']) > 25 else c['title']
                updated = (c['updated_at'] or "")[:19]
                print(f"{c['id']:<4} | {status_display:<13} | {c['category']:<12} | {title_short:<25} | {updated}")

            print("\n--- [LATEST AUDIT LOG EVENTS] ---")
            for a in audits:
                print(f"[{a['timestamp'][:19]}] Action: {a['action']:<15} | Detail: {a['detail']}")

            print("\n" + "=" * 76)
            print("Press Ctrl + C to exit monitor.")

            time.sleep(1)

        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break
        except Exception as e:
            print(f"Read error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
