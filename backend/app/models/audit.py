from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuditLog(Base):
    """SQLAlchemy model for audit_logs table."""
    __tablename__ = "audit_logs"

    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    message = Column(String(500), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=utc_now, index=True)

    # Relationships
    job = relationship("Job", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog audit_id={self.audit_id} job_id='{self.job_id}' event='{self.event_type}'>"
