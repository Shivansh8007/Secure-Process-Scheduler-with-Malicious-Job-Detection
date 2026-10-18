from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.history import ExecutionHistoryResponse
from backend.app.services.worker_service import (
    get_all_execution_history,
    get_job_execution_history
)

router = APIRouter(tags=["Execution History"])


@router.get(
    "/history",
    response_model=List[ExecutionHistoryResponse],
    summary="Retrieve system-wide execution history",
    description="Returns all logged execution records across all jobs, ordered chronologically."
)
def list_system_history(
    limit: int = Query(100, ge=1, le=500, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db)
):
    history_records = get_all_execution_history(db, limit=limit, offset=offset)
    return [ExecutionHistoryResponse.model_validate(h) for h in history_records]


@router.get(
    "/jobs/{job_id}/history",
    response_model=List[ExecutionHistoryResponse],
    summary="Retrieve execution history for a specific job",
    description="Returns all execution runs, outputs, and errors for the specified job ID."
)
def get_job_history(
    job_id: str,
    db: Session = Depends(get_db)
):
    history_records = get_job_execution_history(db, job_id)
    return [ExecutionHistoryResponse.model_validate(h) for h in history_records]
