"""
JobSentinel Scheduler - First-Come, First-Served (FCFS) Algorithm
Non-preemptive CPU scheduling based strictly on arrival time order.
"""

from typing import List
from scheduler.models import JobScheduleItem, ExecutionSlice, ScheduleResult
from scheduler.metrics import calculate_metrics


def schedule_fcfs(job_items: List[JobScheduleItem]) -> ScheduleResult:
    """
    Executes First-Come, First-Served (FCFS) scheduling on a list of jobs.
    
    Tie-breaking rule:
    1. Earlier arrival_time
    2. Alphabetical / numeric string job_id
    """
    if not job_items:
        return ScheduleResult(
            algorithm="FCFS",
            total_jobs=0,
            jobs=[],
            execution_slices=[],
            average_waiting_time=0.0,
            average_turnaround_time=0.0,
            average_response_time=0.0,
            message="No jobs provided for FCFS scheduling."
        )

    # Make a copy of items to avoid mutating input references
    jobs = [item.model_copy() for item in job_items]

    # Deterministic sorting: arrival_time ASC, then job_id ASC
    jobs.sort(key=lambda j: (j.arrival_time, str(j.job_id)))

    current_time = 0.0
    total_busy_time = 0.0
    execution_slices: List[ExecutionSlice] = []

    for order_idx, job in enumerate(jobs, start=1):
        job.execution_order = order_idx

        # If CPU is idle waiting for job arrival, advance clock
        if current_time < job.arrival_time:
            current_time = job.arrival_time

        job.start_time = current_time
        job.completion_time = job.start_time + job.burst_time
        job.turnaround_time = job.completion_time - job.arrival_time
        job.waiting_time = job.turnaround_time - job.burst_time
        job.response_time = job.start_time - job.arrival_time
        job.remaining_time = 0.0

        # Record slice
        slice_duration = job.burst_time
        execution_slices.append(ExecutionSlice(
            job_id=job.job_id,
            start_time=job.start_time,
            end_time=job.completion_time,
            duration=slice_duration
        ))

        total_busy_time += slice_duration
        current_time = job.completion_time

    total_elapsed_time = current_time - (jobs[0].arrival_time if jobs else 0.0)
    metrics = calculate_metrics(jobs, total_elapsed_time, total_busy_time)

    return ScheduleResult(
        algorithm="FCFS",
        quantum=None,
        total_jobs=len(jobs),
        jobs=jobs,
        execution_slices=execution_slices,
        average_waiting_time=metrics.average_waiting_time,
        average_turnaround_time=metrics.average_turnaround_time,
        average_response_time=metrics.average_response_time,
        throughput=metrics.throughput,
        cpu_utilization=metrics.cpu_utilization,
        message=f"Successfully scheduled {len(jobs)} jobs using FCFS."
    )
