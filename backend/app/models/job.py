from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.enums import JobStatus


def utc_now() -> datetime:
    """Return timezone-naive UTC datetime compatible with MySQL DATETIME."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Job(Base):
    """SQLAlchemy model for jobs table."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), unique=True, nullable=False, index=True)
    command = Column(Text, nullable=False)
    arrival_time = Column(Float, nullable=False, index=True)
    burst_time = Column(Float, nullable=False)
    priority = Column(Integer, nullable=False, default=1, index=True)
    status = Column(String(32), nullable=False, default=JobStatus.PENDING.value, index=True)
    algorithm = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    history_records = relationship(
        "ExecutionHistory",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ExecutionHistory.created_at.desc()"
    )
    audit_logs = relationship(
        "AuditLog",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="AuditLog.timestamp.desc()"
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} job_id='{self.job_id}' status='{self.status}'>"
