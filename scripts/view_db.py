import sys
import argparse
from pathlib import Path

# Add project root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import datetime
import pymysql
from backend.app.core.config import settings

def format_val(val):
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val) if val is not None else "NULL"

def print_table(title, rows):
    print(f"\n{'=' * 20} {title} ({len(rows)} rows) {'=' * 20}")
    if not rows:
        print("  (Empty table)")
        return
    
    keys = list(rows[0].keys())
    col_w = {k: max(len(k), max(len(format_val(r[k])) for r in rows)) for k in keys}
    
    header = " | ".join(k.ljust(col_w[k]) for k in keys)
    separator = "-+-".join("-" * col_w[k] for k in keys)
    print(header)
    print(separator)
    for r in rows:
        print(" | ".join(format_val(r[k]).ljust(col_w[k]) for k in keys))

def main():
    parser = argparse.ArgumentParser(description="View JobSentinel MySQL Database contents.")
    parser.add_argument("--table", choices=["jobs", "execution_history", "audit_logs"], help="Specific table to display")
    parser.add_argument("--limit", type=int, default=50, help="Maximum rows to fetch per table (default: 50)")
    args = parser.parse_args()

    print(f"Connecting to MySQL ({settings.DB_HOST}:{settings.DB_PORT}) - Database: {settings.DB_NAME}...")
    try:
        conn = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            charset="utf8mb4"
        )
    except Exception as e:
        print(f"[ERROR] Failed to connect to MySQL: {e}")
        sys.exit(1)

    tables = [args.table] if args.table else ["jobs", "execution_history", "audit_logs"]

    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        for tbl in tables:
            cur.execute(f"SELECT * FROM {tbl} ORDER BY 1 ASC LIMIT %s", (args.limit,))
            rows = cur.fetchall()
            print_table(tbl.upper(), rows)

    conn.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
