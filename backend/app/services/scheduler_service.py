import logging
from typing import List, Dict, Any, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.job import Job
from backend.app.models.enums import JobStatus, AlgorithmType, AuditEventType
from backend.app.schemas.scheduler import (
    SchedulerInputJob,
    JobOrderAssignment,
    JobExecutionMetricItem,
    ExecutionSliceResponse,
    SchedulerScheduleRequest,
    SchedulerScheduleResponse,
    AlgorithmComparisonSummaryItem,
    SchedulerComparisonResponse,
    ProcessComparisonItem,
    ProcessAlgorithmMetric
)
from backend.app.schemas.worker import WorkerResultRequest
from backend.app.schemas.job import JobResponse
from backend.app.services.audit_service import record_audit_log
from backend.app.services.worker_service import (
    start_job_execution,
    record_job_execution_result
)
from backend.app.core.exceptions import InvalidSchedulingAlgorithmException, JobSentinelException
from scheduler.scheduler_manager import SchedulerManager
from scheduler.models import ScheduleResult
import worker

logger = logging.getLogger("jobsentinel.scheduler_service")


def jobs_to_scheduler_input(jobs: List[Job]) -> List[SchedulerInputJob]:
    """Convert DB Job records to the standardized input format expected by Member 2."""
    return [
        SchedulerInputJob(
            job_id=job.job_id,
            arrival_time=job.arrival_time,
            burst_time=job.burst_time,
            priority=job.priority,
            status=JobStatus(job.status)
        )
        for job in jobs
    ]


def compute_schedule_order(
    jobs_input: List[SchedulerInputJob],
    algorithm: AlgorithmType,
    time_quantum: float = 2.0
) -> List[JobOrderAssignment]:
    """
    Computes scheduling order for batch job dispatching.
    Preserves exact Member 1 API contract and test expectations.
    """
    if not jobs_input:
        return []

    if algorithm == AlgorithmType.FCFS:
        sorted_jobs = sorted(jobs_input, key=lambda j: (j.arrival_time, str(j.job_id)))
    elif algorithm == AlgorithmType.SJF:
        # In batch queue: shortest burst time takes precedence
        sorted_jobs = sorted(jobs_input, key=lambda j: (j.burst_time, j.arrival_time, str(j.job_id)))
    elif algorithm == AlgorithmType.PRIORITY:
        # In batch queue: highest priority (lowest number) takes precedence
        sorted_jobs = sorted(jobs_input, key=lambda j: (j.priority, j.arrival_time, str(j.job_id)))
    elif algorithm == AlgorithmType.ROUND_ROBIN:
        sorted_jobs = sorted(jobs_input, key=lambda j: (j.arrival_time, str(j.job_id)))
    else:
        raise InvalidSchedulingAlgorithmException(str(algorithm.value if hasattr(algorithm, "value") else algorithm))

    return [
        JobOrderAssignment(job_id=job.job_id, execution_order=idx + 1)
        for idx, job in enumerate(sorted_jobs)
    ]


def schedule_pending_jobs(
    db: Session,
    request: SchedulerScheduleRequest
) -> SchedulerScheduleResponse:
    """
    Fetches pending jobs, executes OS scheduling algorithm via SchedulerManager,
    records execution order & metrics, updates job status to SCHEDULED,
    and optionally executes jobs through Member 3 worker.
    """
    stmt = select(Job).where(Job.status == JobStatus.PENDING.value)
    if request.job_ids:
        requested_ids = [str(jid) for jid in request.job_ids]
        stmt = stmt.where(Job.job_id.in_(requested_ids))

    # Concurrency safe: order by arrival_time
    stmt = stmt.order_by(Job.arrival_time.asc())
    pending_jobs = list(db.execute(stmt).scalars().all())

    if not pending_jobs:
        return SchedulerScheduleResponse(
            algorithm=request.algorithm,
            time_quantum=request.time_quantum,
            total_scheduled=0,
            schedule=[],
            metrics=[],
            execution_slices=[],
            average_waiting_time=0.0,
            average_turnaround_time=0.0,
            average_response_time=0.0,
            throughput=0.0,
            cpu_utilization=0.0,
            scheduled_jobs=[],
            executed_results=[],
            message="No pending jobs found to schedule."
        )

    # Convert to scheduler input contract
    input_jobs = jobs_to_scheduler_input(pending_jobs)

    # 1. Compute execution sequence per API contract
    order_assignments = compute_schedule_order(
        jobs_input=input_jobs,
        algorithm=request.algorithm,
        time_quantum=request.time_quantum or 2.0
    )
    order_map = {str(item.job_id): item.execution_order for item in order_assignments}

    # 2. Run simulation via Member 2 SchedulerManager for metrics & slices
    quantum_val = request.time_quantum if request.time_quantum is not None else 2.0
    try:
        schedule_res: ScheduleResult = SchedulerManager.schedule(
            jobs=pending_jobs,
            algorithm=request.algorithm.value,
            quantum=quantum_val
        )
    except ValueError as e:
        raise InvalidSchedulingAlgorithmException(str(request.algorithm.value))

    # Match metrics by job_id
    metrics_by_id = {str(j.job_id): j for j in schedule_res.jobs}
    metric_items: List[JobExecutionMetricItem] = []

    for item in order_assignments:
        jid_str = str(item.job_id)
        m = metrics_by_id.get(jid_str)
        metric_items.append(JobExecutionMetricItem(
            job_id=item.job_id,
            execution_order=item.execution_order,
            arrival_time=m.arrival_time if m else 0.0,
            burst_time=m.burst_time if m else 0.0,
            priority=m.priority if m else 1,
            start_time=m.start_time if m else None,
            completion_time=m.completion_time if m else None,
            waiting_time=m.waiting_time if m else None,
            turnaround_time=m.turnaround_time if m else None,
            response_time=m.response_time if m else None
        ))

    # 3. Atomically update jobs to SCHEDULED in DB
    updated_jobs = []
    for job in pending_jobs:
        job.status = JobStatus.SCHEDULED.value
        job.algorithm = request.algorithm.value
        order_num = order_map.get(str(job.job_id), 0)
        record_audit_log(
            db,
            job_id=job.job_id,
            event_type=AuditEventType.JOB_SCHEDULED,
            message=(
                f"Job scheduled with algorithm '{request.algorithm.value}'. "
                f"Execution order: {order_num}"
            )
        )
        updated_jobs.append(job)

    db.commit()
    for job in updated_jobs:
        db.refresh(job)

    # Sort updated jobs by execution order
    updated_jobs.sort(key=lambda j: order_map.get(str(j.job_id), 999999))

    # 4. Optional: Worker execution pipeline
    executed_results: Optional[List[Dict[str, Any]]] = None
    if request.execute_jobs:
        executed_results = []
        worker_id = request.worker_id or "worker-1"
        logger.info("[Integration] Executing %d jobs via Worker '%s'", len(updated_jobs), worker_id)

        for job in updated_jobs:
            logger.info("[Scheduler -> Worker] Dispatching Job '%s'", job.job_id)
            # Step A: Signal start (RUNNING)
            start_job_execution(db, job.job_id, worker_id=worker_id)

            # Step B: Worker executes process
            run_outcome = worker.run_job(
                worker_id=worker_id,
                job_id=job.job_id,
                task=job.command
            )

            # Step C: Record result atomically (COMPLETED / FAILED)
            status_enum = JobStatus.COMPLETED if run_outcome.get("status") == "COMPLETED" else JobStatus.FAILED
            result_req = WorkerResultRequest(
                worker_id=worker_id,
                status=status_enum,
                output=run_outcome.get("output", ""),
                error_message=run_outcome.get("error") or None,
                execution_time=run_outcome.get("execution_time")
            )
            worker_resp = record_job_execution_result(db, job.job_id, result_req)
            executed_results.append(run_outcome)

        # Refresh jobs after execution
        for job in updated_jobs:
            db.refresh(job)

    execution_slices_resp = [
        ExecutionSliceResponse(
            job_id=s.job_id,
            start_time=s.start_time,
            end_time=s.end_time,
            duration=s.duration
        )
        for s in schedule_res.execution_slices
    ]

    return SchedulerScheduleResponse(
        algorithm=request.algorithm,
        time_quantum=request.time_quantum,
        total_scheduled=len(updated_jobs),
        schedule=order_assignments,
        metrics=metric_items,
        execution_slices=execution_slices_resp,
        average_waiting_time=schedule_res.average_waiting_time,
        average_turnaround_time=schedule_res.average_turnaround_time,
        average_response_time=schedule_res.average_response_time,
        throughput=schedule_res.throughput,
        cpu_utilization=schedule_res.cpu_utilization,
        scheduled_jobs=[JobResponse.model_validate(j) for j in updated_jobs],
        executed_results=executed_results,
        message=(
            f"Successfully scheduled and executed {len(updated_jobs)} jobs using {request.algorithm.value}."
            if request.execute_jobs else
            f"Successfully scheduled {len(updated_jobs)} jobs using {request.algorithm.value}."
        )
    )


def compare_all_algorithms(
    db: Session,
    quantum: float = 2.0,
    job_ids: Optional[List[Union[int, str]]] = None,
    scope: str = "pending"
) -> SchedulerComparisonResponse:
    """
    Runs comparative analysis across FCFS, SJF, Round Robin, and Priority.
    Returns:
    - Overall comparison table with measured averages
    - Per-process comparison breakdown across all 4 algorithms
    - Execution Gantt time slices per algorithm
    """
    stmt = select(Job)
    if job_ids:
        requested_ids = [str(jid) for jid in job_ids]
        stmt = stmt.where(Job.job_id.in_(requested_ids))
    elif scope == "pending":
        stmt = stmt.where(Job.status == JobStatus.PENDING.value)
    
    stmt = stmt.order_by(Job.arrival_time.asc())
    target_jobs = list(db.execute(stmt).scalars().all())

    # Fallback to all jobs if pending queue is currently empty
    if not target_jobs and not job_ids:
        all_stmt = select(Job).order_by(Job.created_at.desc()).limit(8)
        target_jobs = list(db.execute(all_stmt).scalars().all())
        target_jobs.sort(key=lambda j: j.arrival_time)

    # If still empty (e.g. brand new DB), provide standard benchmark processes
    if not target_jobs:
        sample_dataset = [
            {"job_id": "P1", "command": "python matrix_mult.py", "arrival_time": 0.0, "burst_time": 5.0, "priority": 2},
            {"job_id": "P2", "command": "python quick_cache.py", "arrival_time": 1.0, "burst_time": 2.0, "priority": 1},
            {"job_id": "P3", "command": "python db_ingest.py", "arrival_time": 2.0, "burst_time": 8.0, "priority": 3},
            {"job_id": "P4", "command": "python log_aggregate.py", "arrival_time": 3.0, "burst_time": 3.0, "priority": 2},
        ]
        target_jobs = sample_dataset

    comparison = SchedulerManager.compare_algorithms(target_jobs, quantum=quantum)

    summary_items = [
        AlgorithmComparisonSummaryItem(
            algorithm=row["algorithm"],
            average_waiting_time=row["average_waiting_time"],
            average_turnaround_time=row["average_turnaround_time"],
            average_response_time=row["average_response_time"],
            throughput=row["throughput"],
            cpu_utilization=row["cpu_utilization"]
        )
        for row in comparison["comparison_table"]
    ]

    process_comparison_items = []
    for p_item in comparison.get("process_comparison", []):
        algo_dict = {}
        for algo_k, algo_v in p_item.get("algorithms", {}).items():
            algo_dict[algo_k] = ProcessAlgorithmMetric(
                order=algo_v.get("order"),
                start_time=algo_v.get("start_time"),
                completion_time=algo_v.get("completion_time"),
                waiting_time=algo_v.get("waiting_time"),
                turnaround_time=algo_v.get("turnaround_time"),
                response_time=algo_v.get("response_time"),
            )
        process_comparison_items.append(
            ProcessComparisonItem(
                job_id=p_item["job_id"],
                command=p_item.get("command", ""),
                arrival_time=p_item["arrival_time"],
                burst_time=p_item["burst_time"],
                priority=p_item["priority"],
                algorithms=algo_dict
            )
        )

    gantt_slices_dict = {}
    for algo_k, slices_list in comparison.get("gantt_charts", {}).items():
        gantt_slices_dict[algo_k] = [
            ExecutionSliceResponse(
                job_id=s["job_id"],
                start_time=s["start_time"],
                end_time=s["end_time"],
                duration=s["duration"]
            )
            for s in slices_list
        ]

    return SchedulerComparisonResponse(
        total_jobs=comparison["total_jobs"],
        quantum_used_for_rr=comparison["quantum_used_for_rr"],
        comparison_table=summary_items,
        recommended_algorithm=comparison["recommended_algorithm"],
        process_comparison=process_comparison_items,
        gantt_charts=gantt_slices_dict,
        detailed_results=comparison["detailed_results"]
    )


def compare_custom_processes(
    processes: List[Any],
    quantum: float = 2.0
) -> SchedulerComparisonResponse:
    """Runs comparative evaluation across a custom list of process inputs."""
    comparison = SchedulerManager.compare_algorithms(processes, quantum=quantum)

    summary_items = [
        AlgorithmComparisonSummaryItem(
            algorithm=row["algorithm"],
            average_waiting_time=row["average_waiting_time"],
            average_turnaround_time=row["average_turnaround_time"],
            average_response_time=row["average_response_time"],
            throughput=row["throughput"],
            cpu_utilization=row["cpu_utilization"]
        )
        for row in comparison["comparison_table"]
    ]

    process_comparison_items = []
    for p_item in comparison.get("process_comparison", []):
        algo_dict = {}
        for algo_k, algo_v in p_item.get("algorithms", {}).items():
            algo_dict[algo_k] = ProcessAlgorithmMetric(
                order=algo_v.get("order"),
                start_time=algo_v.get("start_time"),
                completion_time=algo_v.get("completion_time"),
                waiting_time=algo_v.get("waiting_time"),
                turnaround_time=algo_v.get("turnaround_time"),
                response_time=algo_v.get("response_time"),
            )
        process_comparison_items.append(
            ProcessComparisonItem(
                job_id=p_item["job_id"],
                command=p_item.get("command", ""),
                arrival_time=p_item["arrival_time"],
                burst_time=p_item["burst_time"],
                priority=p_item["priority"],
                algorithms=algo_dict
            )
        )

    gantt_slices_dict = {}
    for algo_k, slices_list in comparison.get("gantt_charts", {}).items():
        gantt_slices_dict[algo_k] = [
            ExecutionSliceResponse(
                job_id=s["job_id"],
                start_time=s["start_time"],
                end_time=s["end_time"],
                duration=s["duration"]
            )
            for s in slices_list
        ]

    return SchedulerComparisonResponse(
        total_jobs=comparison["total_jobs"],
        quantum_used_for_rr=comparison["quantum_used_for_rr"],
        comparison_table=summary_items,
        recommended_algorithm=comparison["recommended_algorithm"],
        process_comparison=process_comparison_items,
        gantt_charts=gantt_slices_dict,
        detailed_results=comparison["detailed_results"]
    )
