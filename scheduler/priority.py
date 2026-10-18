"""
JobSentinel Scheduler - Priority Scheduling Algorithm (Non-preemptive)
CPU scheduling based on priority level where lower numerical value represents higher priority.
Implements arrival-aware ready queue simulation and deterministic tie-breaking.
"""

from typing import List
from scheduler.models import JobScheduleItem, ExecutionSlice, ScheduleResult
from scheduler.metrics import calculate_metrics


def schedule_priority(job_items: List[JobScheduleItem]) -> ScheduleResult:
    """
    Executes Non-Preemptive Priority scheduling on a list of jobs.
    
    Priority Convention:
    - Lower numerical value = Higher priority (e.g. Priority 1 is higher priority than Priority 5).
    
    Deterministic Tie-Breaking Hierarchy:
    1. Highest Priority (Lowest numerical `priority` value)
    2. Earlier `arrival_time`
    3. Alphabetical / numeric string `job_id`
    """
    if not job_items:
        return ScheduleResult(
            algorithm="PRIORITY",
            total_jobs=0,
            jobs=[],
            execution_slices=[],
            average_waiting_time=0.0,
            average_turnaround_time=0.0,
            average_response_time=0.0,
            message="No jobs provided for Priority scheduling."
        )

    uncompleted = [item.model_copy() for item in job_items]
    scheduled_order: List[JobScheduleItem] = []
    execution_slices: List[ExecutionSlice] = []

    current_time = 0.0
    total_busy_time = 0.0
    earliest_arrival = min(j.arrival_time for j in uncompleted)
    if current_time < earliest_arrival:
        current_time = earliest_arrival

    order_counter = 1
    while uncompleted:
        # Ready pool: jobs that have arrived by current_time
        ready_jobs = [j for j in uncompleted if j.arrival_time <= current_time]

        if not ready_jobs:
            # CPU is idle: advance to next job arrival
            current_time = min(j.arrival_time for j in uncompleted)
            ready_jobs = [j for j in uncompleted if j.arrival_time <= current_time]

        # Select highest priority (lowest number), breaking ties by arrival_time, then job_id
        selected_job = min(
            ready_jobs,
            key=lambda j: (j.priority, j.arrival_time, str(j.job_id))
        )
        uncompleted.remove(selected_job)

        # Run selected job to completion
        selected_job.execution_order = order_counter
        order_counter += 1

        selected_job.start_time = current_time
        selected_job.completion_time = current_time + selected_job.burst_time
        selected_job.turnaround_time = selected_job.completion_time - selected_job.arrival_time
        selected_job.waiting_time = selected_job.turnaround_time - selected_job.burst_time
        selected_job.response_time = selected_job.start_time - selected_job.arrival_time
        selected_job.remaining_time = 0.0

        # Record slice
        slice_duration = selected_job.burst_time
        execution_slices.append(ExecutionSlice(
            job_id=selected_job.job_id,
            start_time=selected_job.start_time,
            end_time=selected_job.completion_time,
            duration=slice_duration
        ))

        total_busy_time += slice_duration
        current_time = selected_job.completion_time
        scheduled_order.append(selected_job)

    total_elapsed_time = current_time - earliest_arrival
    metrics = calculate_metrics(scheduled_order, total_elapsed_time, total_busy_time)

    return ScheduleResult(
        algorithm="PRIORITY",
        quantum=None,
        total_jobs=len(scheduled_order),
        jobs=scheduled_order,
        execution_slices=execution_slices,
        average_waiting_time=metrics.average_waiting_time,
        average_turnaround_time=metrics.average_turnaround_time,
        average_response_time=metrics.average_response_time,
        throughput=metrics.throughput,
        cpu_utilization=metrics.cpu_utilization,
        message=f"Successfully scheduled {len(scheduled_order)} jobs using Priority Scheduling."
    )
