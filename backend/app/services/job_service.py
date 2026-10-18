import time
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.app.models.job import Job
from backend.app.models.enums import JobStatus, AuditEventType
from backend.app.schemas.job import JobCreate
from backend.app.services.audit_service import record_audit_log
from backend.app.core.exceptions import (
    JobNotFoundException,
    JobAlreadyExistsException,
    InvalidStatusTransitionException,
)
from backend.app.core.logging import logger

# Valid lifecycle state transitions mapping
ALLOWED_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.SCHEDULED, JobStatus.FAILED},
    JobStatus.SCHEDULED: {JobStatus.RUNNING, JobStatus.FAILED},
    JobStatus.RUNNING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),  # Terminal state
    JobStatus.FAILED: set(),     # Terminal state
    JobStatus.QUARANTINED: set() # Extension placeholder
}


def generate_next_job_id(db: Session) -> str:
    """Generate a clean sequential job identifier (e.g. 101, 102, 103...)."""
    # Look for existing numeric job_ids to increment sequentially
    all_jobs = db.execute(select(Job.job_id)).scalars().all()
    numeric_ids = []
    for jid in all_jobs:
        try:
            numeric_ids.append(int(jid))
        except ValueError:
            continue
            
    if numeric_ids:
        next_id = max(numeric_ids) + 1
    else:
        next_id = 101
    return str(next_id)


def validate_status_transition(current_status: JobStatus, target_status: JobStatus, job_id: str) -> None:
    """Validate that the requested status transition conforms to the lifecycle state machine."""
    if current_status == target_status:
        return

    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        logger.warning(
            "Rejected invalid lifecycle transition for Job '%s': %s -> %s",
            job_id, current_status.value, target_status.value
        )
        raise InvalidStatusTransitionException(
            current_status=current_status.value,
            target_status=target_status.value,
            job_id=job_id
        )


def create_job(db: Session, job_in: JobCreate) -> Job:
    """Submit a new job, assign unique job_id and arrival time, persist in MySQL with status PENDING."""
    # Determine unique job_id
    if job_in.job_id is not None:
        assigned_id = str(job_in.job_id)
        existing = db.execute(select(Job).where(Job.job_id == assigned_id)).scalar_one_or_none()
        if existing:
            raise JobAlreadyExistsException(assigned_id)
    else:
        assigned_id = generate_next_job_id(db)

    # Set arrival time: default to current timestamp if not specified
    arrival = float(job_in.arrival_time) if job_in.arrival_time is not None else round(time.time(), 3)

    new_job = Job(
        job_id=assigned_id,
        command=job_in.command.strip(),
        arrival_time=arrival,
        burst_time=float(job_in.burst_time),
        priority=int(job_in.priority),
        status=JobStatus.PENDING.value,
        algorithm=None
    )
    
    db.add(new_job)
    record_audit_log(
        db,
        job_id=assigned_id,
        event_type=AuditEventType.JOB_CREATED,
        message=f"Job submitted with arrival_time={arrival}, burst_time={job_in.burst_time}, priority={job_in.priority}"
    )
    db.commit()
    db.refresh(new_job)
    logger.info("Successfully submitted and stored Job '%s' with status PENDING", assigned_id)
    return new_job


def get_job_by_id(db: Session, job_id: str) -> Job:
    """Retrieve a single job by its unique job_id or raise JobNotFoundException."""
    job = db.execute(select(Job).where(Job.job_id == str(job_id))).scalar_one_or_none()
    if not job:
        raise JobNotFoundException(str(job_id))
    return job


def get_all_jobs(db: Session, status: Optional[JobStatus] = None, limit: int = 100, offset: int = 0) -> List[Job]:
    """Retrieve a list of jobs, optionally filtered by status."""
    stmt = select(Job)
    if status is not None:
        stmt = stmt.where(Job.status == status.value)
    stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_pending_jobs(db: Session) -> List[Job]:
    """Retrieve all jobs currently ready for scheduling (status == PENDING) ordered by arrival time."""
    stmt = select(Job).where(Job.status == JobStatus.PENDING.value).order_by(Job.arrival_time.asc())
    return list(db.execute(stmt).scalars().all())


def update_job_status(db: Session, job_id: str, new_status: JobStatus) -> Job:
    """Safely transition job status with lifecycle validation and audit logging."""
    job = get_job_by_id(db, job_id)
    current_status = JobStatus(job.status)

    validate_status_transition(current_status, new_status, job.job_id)

    job.status = new_status.value
    
    # Audit log
    audit_event = AuditEventType.JOB_SCHEDULED if new_status == JobStatus.SCHEDULED else (
        AuditEventType.JOB_STARTED if new_status == JobStatus.RUNNING else (
            AuditEventType.JOB_COMPLETED if new_status == JobStatus.COMPLETED else AuditEventType.JOB_FAILED
        )
    )
    record_audit_log(
        db,
        job_id=job.job_id,
        event_type=audit_event,
        message=f"Job status transitioned from {current_status.value} to {new_status.value}"
    )
    
    db.commit()
    db.refresh(job)
    logger.info("Job '%s' status updated to %s", job_id, new_status.value)
    return job
