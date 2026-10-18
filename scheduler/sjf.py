"""
JobSentinel Scheduler - Shortest Job First (SJF) Algorithm
Non-preemptive CPU scheduling selecting the available job with the smallest burst time.
Properly simulates timeline and dynamic ready queue when jobs arrive at different times.
"""

from typing import List
from scheduler.models import JobScheduleItem, ExecutionSlice, ScheduleResult
from scheduler.metrics import calculate_metrics


def schedule_sjf(job_items: List[JobScheduleItem]) -> ScheduleResult:
    """
    Executes Non-Preemptive Shortest Job First (SJF) scheduling.
    
    Decision rule at time t:
    Filter uncompleted jobs where arrival_time <= t.
    Select job with:
    1. Smallest burst_time
    2. Earlier arrival_time (tie-breaker)
    3. Alphabetical / numeric string job_id (tie-breaker)
    """
    if not job_items:
        return ScheduleResult(
            algorithm="SJF",
            total_jobs=0,
            jobs=[],
            execution_slices=[],
            average_waiting_time=0.0,
            average_turnaround_time=0.0,
            average_response_time=0.0,
            message="No jobs provided for SJF scheduling."
        )

    # Work with copies
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
            # CPU is idle: jump forward to the next earliest arriving job
            current_time = min(j.arrival_time for j in uncompleted)
            ready_jobs = [j for j in uncompleted if j.arrival_time <= current_time]

        # Select smallest burst time, breaking ties deterministically
        selected_job = min(
            ready_jobs,
            key=lambda j: (j.burst_time, j.arrival_time, str(j.job_id))
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
        algorithm="SJF",
        quantum=None,
        total_jobs=len(scheduled_order),
        jobs=scheduled_order,
        execution_slices=execution_slices,
        average_waiting_time=metrics.average_waiting_time,
        average_turnaround_time=metrics.average_turnaround_time,
        average_response_time=metrics.average_response_time,
        throughput=metrics.throughput,
        cpu_utilization=metrics.cpu_utilization,
        message=f"Successfully scheduled {len(scheduled_order)} jobs using SJF."
    )
