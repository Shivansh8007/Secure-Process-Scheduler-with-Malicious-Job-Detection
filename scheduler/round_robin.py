"""
JobSentinel Scheduler - Preemptive Round Robin (RR) Algorithm
Preemptive CPU scheduling using a configurable time quantum, maintaining
an active ready queue, tracking remaining burst times, and logging discrete execution slices.
"""

from collections import deque
from typing import List, Optional, Dict
from scheduler.models import JobScheduleItem, ExecutionSlice, ScheduleResult
from scheduler.metrics import calculate_metrics


def schedule_round_robin(
    job_items: List[JobScheduleItem],
    quantum: float = 2.0
) -> ScheduleResult:
    """
    Executes Preemptive Round Robin scheduling on a list of jobs.
    
    Parameters:
    - job_items: List of jobs with arrival_time, burst_time, priority, job_id.
    - quantum: Time quantum duration (must be > 0).
    """
    if quantum <= 0:
        raise ValueError(f"Time quantum must be strictly positive (> 0), received: {quantum}")

    if not job_items:
        return ScheduleResult(
            algorithm="ROUND_ROBIN",
            quantum=quantum,
            total_jobs=0,
            jobs=[],
            execution_slices=[],
            average_waiting_time=0.0,
            average_turnaround_time=0.0,
            average_response_time=0.0,
            message="No jobs provided for Round Robin scheduling."
        )

    # Initialize job copies and state
    all_jobs: Dict[str, JobScheduleItem] = {}
    unvisited: List[JobScheduleItem] = []
    
    for item in job_items:
        copy_j = item.model_copy()
        copy_j.remaining_time = float(copy_j.burst_time)
        copy_j.start_time = None
        copy_j.completion_time = None
        copy_j.waiting_time = None
        copy_j.turnaround_time = None
        copy_j.response_time = None
        all_jobs[str(copy_j.job_id)] = copy_j
        unvisited.append(copy_j)

    # Sort unvisited by arrival time, then job_id
    unvisited.sort(key=lambda j: (j.arrival_time, str(j.job_id)))

    current_time = unvisited[0].arrival_time
    ready_queue: deque[JobScheduleItem] = deque()
    execution_slices: List[ExecutionSlice] = []
    completed_jobs: List[JobScheduleItem] = []
    total_busy_time = 0.0

    # Enqueue jobs that have arrived at or before initial current_time
    arrived_initially = [j for j in unvisited if j.arrival_time <= current_time]
    for j in arrived_initially:
        ready_queue.append(j)
        unvisited.remove(j)

    order_counter = 1
    while ready_queue or unvisited:
        if not ready_queue:
            # CPU is idle: advance time to the next earliest arrival
            next_arrival = min(j.arrival_time for j in unvisited)
            current_time = next_arrival
            arrived_now = [j for j in unvisited if j.arrival_time <= current_time]
            for j in arrived_now:
                ready_queue.append(j)
                unvisited.remove(j)

        # Dequeue the next process from the ready queue
        current_job = ready_queue.popleft()

        # Record first start time (for Response Time)
        if current_job.start_time is None:
            current_job.start_time = current_time
            current_job.response_time = current_time - current_job.arrival_time

        # Calculate time slice
        slice_duration = min(quantum, current_job.remaining_time)
        next_time = current_time + slice_duration

        # Record discrete execution slice (useful for Gantt / visualization)
        execution_slices.append(ExecutionSlice(
            job_id=current_job.job_id,
            start_time=current_time,
            end_time=next_time,
            duration=slice_duration
        ))

        total_busy_time += slice_duration
        current_job.remaining_time -= slice_duration

        # Check for newly arrived jobs during this time slice [current_time, next_time]
        # Standard OS rule: newly arriving jobs enter the ready queue BEFORE a preempted job
        arrived_during_slice = [j for j in unvisited if j.arrival_time <= next_time]
        for j in arrived_during_slice:
            ready_queue.append(j)
            unvisited.remove(j)

        current_time = next_time

        # If process still requires CPU burst, re-enqueue at tail
        if current_job.remaining_time > 1e-6:
            ready_queue.append(current_job)
        else:
            # Process completed
            current_job.remaining_time = 0.0
            current_job.completion_time = current_time
            current_job.turnaround_time = current_job.completion_time - current_job.arrival_time
            current_job.waiting_time = current_job.turnaround_time - current_job.burst_time
            current_job.execution_order = order_counter
            order_counter += 1
            completed_jobs.append(current_job)

    # Sort completed jobs according to execution completion or initial arrival
    earliest_arrival = min(j.arrival_time for j in job_items)
    total_elapsed_time = current_time - earliest_arrival
    metrics = calculate_metrics(completed_jobs, total_elapsed_time, total_busy_time)

    # Order completed jobs for response display by execution_order
    completed_jobs.sort(key=lambda j: j.execution_order or 0)

    return ScheduleResult(
        algorithm="ROUND_ROBIN",
        quantum=quantum,
        total_jobs=len(completed_jobs),
        jobs=completed_jobs,
        execution_slices=execution_slices,
        average_waiting_time=metrics.average_waiting_time,
        average_turnaround_time=metrics.average_turnaround_time,
        average_response_time=metrics.average_response_time,
        throughput=metrics.throughput,
        cpu_utilization=metrics.cpu_utilization,
        message=f"Successfully scheduled {len(completed_jobs)} jobs using Round Robin (quantum={quantum})."
    )
