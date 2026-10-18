from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.models.enums import JobStatus
from backend.app.schemas.job import (
    JobCreate,
    JobResponse,
    JobSubmissionResponse,
    JobStatusUpdate
)
from backend.app.services.job_service import (
    create_job,
    get_job_by_id,
    get_all_jobs,
    get_pending_jobs,
    update_job_status
)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new job",
    description="Validates input, assigns arrival time and a unique job_id, sets status to PENDING, and stores in MySQL."
)
def submit_job(job_in: JobCreate, db: Session = Depends(get_db)):
    created = create_job(db, job_in)
    return JobSubmissionResponse(
        job_id=created.job_id,
        status=JobStatus(created.status),
        message="Job submitted successfully",
        job=JobResponse.model_validate(created)
    )


@router.get(
    "",
    response_model=List[JobResponse],
    summary="Retrieve all jobs",
    description="Returns a list of jobs, optionally filtered by status with pagination."
)
def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by status (PENDING, SCHEDULED, RUNNING, COMPLETED, FAILED)"),
    limit: int = Query(100, ge=1, le=500, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db)
):
    jobs = get_all_jobs(db, status=status, limit=limit, offset=offset)
    return [JobResponse.model_validate(j) for j in jobs]


@router.get(
    "/pending",
    response_model=List[JobResponse],
    summary="Retrieve pending jobs for scheduling",
    description="Returns all jobs currently in PENDING status ordered by arrival time, ready to be scheduled."
)
def list_pending_jobs(db: Session = Depends(get_db)):
    jobs = get_pending_jobs(db)
    return [JobResponse.model_validate(j) for j in jobs]


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Retrieve a specific job",
    description="Fetch a job by its unique identifier (e.g. 101)."
)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = get_job_by_id(db, job_id)
    return JobResponse.model_validate(job)


@router.patch(
    "/{job_id}/status",
    response_model=JobResponse,
    summary="Update job status with lifecycle validation",
    description="Transitions job status while validating that the state transition follows allowed lifecycle paths."
)
def change_job_status(job_id: str, update_in: JobStatusUpdate, db: Session = Depends(get_db)):
    updated = update_job_status(db, job_id, update_in.status)
    return JobResponse.model_validate(updated)
