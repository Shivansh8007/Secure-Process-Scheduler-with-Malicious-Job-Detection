import sys
from pathlib import Path
from urllib.parse import quote_plus

# Add project root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pymysql
from sqlalchemy import create_engine

from backend.app.core.config import settings
from backend.app.core.database import Base
# Import all models to register them on Base.metadata
import backend.app.models


def initialize_mysql():
    """Ensure database exists and create tables via SQLAlchemy Base metadata."""
    print("=" * 60)
    print("JobSentinel - MySQL Database Initialization")
    print("=" * 60)
    print(f"Target DB Host: {settings.DB_HOST}:{settings.DB_PORT}")
    print(f"Target DB Name: {settings.DB_NAME}")
    print(f"Target DB User: {settings.DB_USER}")
    
    # Step 1: Connect to MySQL server to ensure DB exists
    try:
        conn = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            charset="utf8mb4"
        )
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        conn.commit()
        conn.close()
        print(f"[SUCCESS] Database '{settings.DB_NAME}' verified/created.")
    except Exception as e:
        print(f"[ERROR] Could not connect to MySQL server: {e}")
        print("Please check your DB_USER, DB_PASSWORD, and DB_PORT in .env")
        return False

    # Step 2: Create all tables via SQLAlchemy
    try:
        engine = create_engine(settings.sync_database_url)
        Base.metadata.create_all(bind=engine)
        print("[SUCCESS] All tables (jobs, execution_history, audit_logs) created successfully!")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to create tables: {e}")
        return False


if __name__ == "__main__":
    success = initialize_mysql()
    sys.exit(0 if success else 1)
