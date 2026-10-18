from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ExecutionHistory(Base):
    """SQLAlchemy model for execution_history table."""
    __tablename__ = "execution_history"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    execution_time = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)

    # Relationships
    job = relationship("Job", back_populates="history_records")

    def __repr__(self) -> str:
        return f"<ExecutionHistory history_id={self.history_id} job_id='{self.job_id}' worker='{self.worker_id}'>"
