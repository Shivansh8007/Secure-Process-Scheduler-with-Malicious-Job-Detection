from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.job import JobResponse
from backend.app.schemas.worker import (
    WorkerStartRequest,
    WorkerResultRequest,
    WorkerResultResponse
)
from backend.app.services.worker_service import (
    start_job_execution,
    record_job_execution_result
)

router = APIRouter(prefix="/jobs", tags=["Worker Integration"])


@router.patch(
    "/{job_id}/start",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Worker signals execution start",
    description="Transitions job status from SCHEDULED to RUNNING, records started_at timestamp and worker audit log."
)
def start_job(
    job_id: str,
    start_in: WorkerStartRequest = WorkerStartRequest(),
    db: Session = Depends(get_db)
):
    job = start_job_execution(db, job_id, worker_id=start_in.worker_id)
    return JobResponse.model_validate(job)


@router.post(
    "/{job_id}/result",
    response_model=WorkerResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Worker reports execution outcome (Member 3 contract)",
    description=(
        "Stores the final execution outcome (COMPLETED or FAILED), persists stdout/stderr, records execution time, "
        "and creates an immutable history and audit log entry within an atomic transaction."
    )
)
def submit_job_result(
    job_id: str,
    result_in: WorkerResultRequest,
    db: Session = Depends(get_db)
):
    return record_job_execution_result(db, job_id, result_in)
