from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.job import Job
from backend.app.models.history import ExecutionHistory
from backend.app.models.enums import JobStatus, AuditEventType
from backend.app.schemas.worker import (
    WorkerResultRequest,
    WorkerResultResponse
)
from backend.app.schemas.job import JobResponse
from backend.app.services.job_service import get_job_by_id, validate_status_transition
from backend.app.services.audit_service import record_audit_log
from backend.app.core.exceptions import InvalidStatusTransitionException, JobSentinelException
from backend.app.core.logging import logger


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def start_job_execution(db: Session, job_id: str, worker_id: str = "worker-1") -> Job:
    """
    Worker starts job execution.
    Transitions status to RUNNING, records started_at timestamp, writes audit log, and commits.
    """
    job = get_job_by_id(db, job_id)
    current_status = JobStatus(job.status)

    # Validate transition to RUNNING
    validate_status_transition(current_status, JobStatus.RUNNING, job.job_id)

    job.status = JobStatus.RUNNING.value
    job.started_at = utc_now()

    record_audit_log(
        db,
        job_id=job.job_id,
        event_type=AuditEventType.JOB_STARTED,
        message=f"Job execution started by worker '{worker_id}'"
    )

    db.commit()
    db.refresh(job)
    logger.info("Job '%s' marked RUNNING by worker '%s'", job_id, worker_id)
    return job


def record_job_execution_result(
    db: Session,
    job_id: str,
    result_in: WorkerResultRequest
) -> WorkerResultResponse:
    """
    Worker completes or fails job execution.
    Performs an atomic transaction:
    1. Updates job status (COMPLETED or FAILED) and completed_at timestamp
    2. Inserts an execution_history row preserving outputs, errors, and execution metrics
    3. Appends an audit log entry
    4. Commits the transaction atomically
    """
    job = get_job_by_id(db, job_id)
    current_status = JobStatus(job.status)

    if result_in.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
        raise JobSentinelException(
            f"Worker result status must be COMPLETED or FAILED, received: {result_in.status.value}",
            status_code=422
        )

    validate_status_transition(current_status, result_in.status, job.job_id)

    completion_time = utc_now()
    started_time = job.started_at or completion_time

    # Calculate execution time if not explicitly provided
    if result_in.execution_time is not None:
        exec_time = float(result_in.execution_time)
    else:
        exec_time = round((completion_time - started_time).total_seconds(), 4)

    # 1. Update job record
    job.status = result_in.status.value
    job.completed_at = completion_time

    # 2. Insert execution history
    history_entry = ExecutionHistory(
        job_id=job.job_id,
        worker_id=result_in.worker_id,
        status=result_in.status.value,
        output=result_in.output,
        error_message=result_in.error_message,
        started_at=started_time,
        completed_at=completion_time,
        execution_time=exec_time
    )
    db.add(history_entry)

    # 3. Add audit log
    audit_event = AuditEventType.JOB_COMPLETED if result_in.status == JobStatus.COMPLETED else AuditEventType.JOB_FAILED
    record_audit_log(
        db,
        job_id=job.job_id,
        event_type=audit_event,
        message=(
            f"Worker '{result_in.worker_id}' finished execution with status {result_in.status.value}. "
            f"Execution time: {exec_time}s"
        )
    )

    # 4. Atomic Commit
    db.commit()
    db.refresh(job)

    logger.info(
        "Job '%s' execution finished by worker '%s' with status %s in %.2fs",
        job_id, result_in.worker_id, result_in.status.value, exec_time
    )

    return WorkerResultResponse(
        job_id=job.job_id,
        status=JobStatus(job.status),
        worker_id=result_in.worker_id,
        execution_time=exec_time,
        message=f"Execution result stored successfully with status {job.status}.",
        job=JobResponse.model_validate(job)
    )


def get_job_execution_history(db: Session, job_id: str) -> List[ExecutionHistory]:
    """Retrieve execution history records for a specific job."""
    # Ensure job exists
    get_job_by_id(db, job_id)
    stmt = (
        select(ExecutionHistory)
        .where(ExecutionHistory.job_id == str(job_id))
        .order_by(ExecutionHistory.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_all_execution_history(db: Session, limit: int = 100, offset: int = 0) -> List[ExecutionHistory]:
    """Retrieve system-wide execution history ordered chronologically."""
    stmt = (
        select(ExecutionHistory)
        .order_by(ExecutionHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())
