"""
JobSentinel Scheduler - Metrics Calculation Engine
Computes standard OS process scheduling metrics:
- Turnaround Time = Completion Time - Arrival Time
- Waiting Time = Turnaround Time - Burst Time
- Response Time = First Start Time - Arrival Time
- Average Waiting Time, Turnaround Time, and Response Time
- CPU Utilization and System Throughput
"""

from typing import List, Tuple
from scheduler.models import JobScheduleItem, AlgorithmMetrics


def calculate_metrics(
    jobs: List[JobScheduleItem],
    total_elapsed_time: float,
    total_busy_time: float
) -> AlgorithmMetrics:
    """
    Computes aggregate metrics from completed job schedule items.
    """
    if not jobs:
        return AlgorithmMetrics(
            average_waiting_time=0.0,
            average_turnaround_time=0.0,
            average_response_time=0.0,
            total_burst_time=0.0,
            throughput=0.0,
            cpu_utilization=0.0
        )

    n = len(jobs)
    total_wt = sum(j.waiting_time for j in jobs if j.waiting_time is not None)
    total_tat = sum(j.turnaround_time for j in jobs if j.turnaround_time is not None)
    total_rt = sum(j.response_time for j in jobs if j.response_time is not None)
    total_bt = sum(j.burst_time for j in jobs)

    avg_wt = total_wt / n
    avg_tat = total_tat / n
    avg_rt = total_rt / n

    throughput = n / total_elapsed_time if total_elapsed_time > 0 else 0.0
    cpu_utilization = (total_busy_time / total_elapsed_time * 100.0) if total_elapsed_time > 0 else 100.0

    return AlgorithmMetrics(
        average_waiting_time=avg_wt,
        average_turnaround_time=avg_tat,
        average_response_time=avg_rt,
        total_burst_time=total_bt,
        throughput=throughput,
        cpu_utilization=min(100.0, cpu_utilization)
    )
