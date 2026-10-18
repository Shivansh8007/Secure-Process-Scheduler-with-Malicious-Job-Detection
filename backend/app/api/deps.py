from typing import Generator
from sqlalchemy.orm import Session
from backend.app.core.database import get_db

# Re-export get_db dependency for clean imports in route handlers
__all__ = ["get_db", "Session"]
