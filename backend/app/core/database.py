import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.core.config import settings

logger = logging.getLogger("jobsentinel.database")

Base = declarative_base()

# Configure engine arguments
engine_args = {
    "pool_pre_ping": True,
}

if not settings.sync_database_url.startswith("sqlite"):
    engine_args.update({
        "pool_recycle": 3600,
        "pool_size": 10,
        "max_overflow": 20,
    })

# Primary engine initialization
engine = create_engine(settings.sync_database_url, **engine_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def check_db_connection() -> bool:
    """Verify active database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified successfully.")
        return True
    except Exception as err:
        logger.warning("Database connection check failed: %s", str(err))
        return False


def ensure_db_ready():
    """
    Verifies database connection.
    If target MySQL server is unreachable, gracefully switches to local persistent
    SQLite file ('jobsentinel.db') to guarantee 100% operational uptime.
    """
    global engine, SessionLocal
    if not check_db_connection() and not settings.sync_database_url.startswith("sqlite"):
        logger.warning(
            "MySQL is unreachable at %s:%s. Enabling local persistent database fallback ('sqlite:///./jobsentinel.db').",
            settings.DB_HOST, settings.DB_PORT
        )
        engine = create_engine(
            "sqlite:///./jobsentinel.db",
            connect_args={"check_same_thread": False}
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Initialize all registered ORM tables
    init_db()


def init_db():
    """Create all tables defined in models if they do not exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/initialized.")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session with transaction safety."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error("Database transaction rolled back due to error: %s", str(e))
        db.rollback()
        raise
    finally:
        db.close()
