from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.api.deps import get_db
from backend.app.models.audit import AuditLog
from backend.app.schemas.audit import AuditLogResponse
from backend.app.services.job_service import get_job_by_id

router = APIRouter(tags=["Audit Logs"])


@router.get(
    "/audit-logs",
    response_model=List[AuditLogResponse],
    summary="Retrieve all audit logs",
    description="Returns chronological audit logs of all lifecycle transitions across jobs."
)
def list_all_audit_logs(
    limit: int = Query(100, ge=1, le=500, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    db: Session = Depends(get_db)
):
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
    logs = list(db.execute(stmt).scalars().all())
    return [AuditLogResponse.model_validate(l) for l in logs]


@router.get(
    "/jobs/{job_id}/audit-logs",
    response_model=List[AuditLogResponse],
    summary="Retrieve audit logs for a specific job",
    description="Returns all lifecycle audit events logged for the specified job ID."
)
def get_job_audit_logs(
    job_id: str,
    db: Session = Depends(get_db)
):
    # Verify job exists
    get_job_by_id(db, job_id)
    stmt = select(AuditLog).where(AuditLog.job_id == str(job_id)).order_by(AuditLog.timestamp.desc())
    logs = list(db.execute(stmt).scalars().all())
    return [AuditLogResponse.model_validate(l) for l in logs]
