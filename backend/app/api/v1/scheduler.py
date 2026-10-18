from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.scheduler import (
    SchedulerScheduleRequest,
    SchedulerScheduleResponse,
    SchedulerInputJob,
    SchedulerComparisonResponse,
    CustomComparisonRequest
)
from backend.app.services.job_service import get_pending_jobs
from backend.app.services.scheduler_service import (
    schedule_pending_jobs,
    jobs_to_scheduler_input,
    compare_all_algorithms,
    compare_custom_processes
)

router = APIRouter(tags=["Scheduler Integration"])


@router.post(
    "/jobs/schedule",
    response_model=SchedulerScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="Schedule pending jobs using selected algorithm",
    description=(
        "Applies a CPU scheduling algorithm (FCFS, SJF, ROUND_ROBIN, PRIORITY) to pending jobs. "
        "Transitions jobs to SCHEDULED, records execution order and metrics, logs audit events, "
        "and optionally executes jobs via Member 3 worker."
    )
)
@router.post(
    "/schedule",
    response_model=SchedulerScheduleResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False
)
def trigger_scheduling(
    request: SchedulerScheduleRequest,
    db: Session = Depends(get_db)
):
    return schedule_pending_jobs(db, request)


@router.get(
    "/jobs/schedule/input",
    response_model=List[SchedulerInputJob],
    summary="Fetch input dataset for scheduler algorithms (Member 2 contract)",
    description="Returns all pending jobs formatted specifically for Member 2's scheduling algorithms."
)
def get_scheduler_input_data(db: Session = Depends(get_db)):
    pending = get_pending_jobs(db)
    return jobs_to_scheduler_input(pending)


@router.get(
    "/jobs/schedule/compare",
    response_model=SchedulerComparisonResponse,
    summary="Compare performance across all 4 scheduling algorithms along processes",
    description="Simulates FCFS, SJF, Round Robin, and Priority on jobs and compares performance metrics overall and along individual processes."
)
@router.get(
    "/schedule/compare",
    response_model=SchedulerComparisonResponse,
    include_in_schema=False
)
def compare_algorithms_endpoint(
    quantum: float = Query(2.0, gt=0, description="Time quantum for Round Robin comparison"),
    scope: str = Query("pending", description="Scope of jobs: 'pending' or 'all'"),
    db: Session = Depends(get_db)
):
    return compare_all_algorithms(db, quantum=quantum, scope=scope)


@router.post(
    "/jobs/schedule/compare/custom",
    response_model=SchedulerComparisonResponse,
    summary="Compare all 4 algorithms on custom simulation processes",
    description="Simulates FCFS, SJF, Round Robin, and Priority on custom user-provided processes."
)
def compare_custom_processes_endpoint(
    request: CustomComparisonRequest
):
    return compare_custom_processes(request.processes, quantum=request.quantum)
