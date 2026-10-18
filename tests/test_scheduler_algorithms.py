"""
Unit Tests for JobSentinel OS Scheduling Module (Phase 2 - Member 2)
Covers FCFS, SJF, Round Robin, Priority Scheduling, and Comparative Evaluation.
"""

import pytest
from scheduler.models import JobScheduleItem
from scheduler.fcfs import schedule_fcfs
from scheduler.sjf import schedule_sjf
from scheduler.round_robin import schedule_round_robin
from scheduler.priority import schedule_priority
from scheduler.scheduler_manager import SchedulerManager


# ====================================================================
# FCFS Tests
# ====================================================================

def test_fcfs_single_job():
    """FCFS with a single job."""
    jobs = [JobScheduleItem(job_id="J1", arrival_time=0.0, burst_time=5.0, priority=1)]
    result = schedule_fcfs(jobs)

    assert result.total_jobs == 1
    assert result.jobs[0].job_id == "J1"
    assert result.jobs[0].start_time == 0.0
    assert result.jobs[0].completion_time == 5.0
    assert result.jobs[0].waiting_time == 0.0
    assert result.jobs[0].turnaround_time == 5.0
    assert result.jobs[0].response_time == 0.0
    assert result.average_waiting_time == 0.0
    assert result.average_turnaround_time == 5.0


def test_fcfs_multiple_jobs_different_arrival_times():
    """
    FCFS with multiple jobs and staggered arrivals.
    J1: AT=0, BT=4 -> Starts=0, Ends=4, TAT=4, WT=0, RT=0
    J2: AT=2, BT=3 -> Starts=4, Ends=7, TAT=5, WT=2, RT=2
    J3: AT=4, BT=1 -> Starts=7, Ends=8, TAT=4, WT=3, RT=3
    """
    jobs = [
        JobScheduleItem(job_id="J1", arrival_time=0.0, burst_time=4.0, priority=1),
        JobScheduleItem(job_id="J2", arrival_time=2.0, burst_time=3.0, priority=1),
        JobScheduleItem(job_id="J3", arrival_time=4.0, burst_time=1.0, priority=1),
    ]
    result = schedule_fcfs(jobs)

    assert [j.job_id for j in result.jobs] == ["J1", "J2", "J3"]
    j1, j2, j3 = result.jobs
    assert (j1.start_time, j1.completion_time, j1.waiting_time) == (0.0, 4.0, 0.0)
    assert (j2.start_time, j2.completion_time, j2.waiting_time) == (4.0, 7.0, 2.0)
    assert (j3.start_time, j3.completion_time, j3.waiting_time) == (7.0, 8.0, 3.0)

    # Avg WT = (0 + 2 + 3) / 3 = 1.67
    assert result.average_waiting_time == pytest.approx(1.67, 0.01)
    # Avg TAT = (4 + 5 + 4) / 3 = 4.33
    assert result.average_turnaround_time == pytest.approx(4.33, 0.01)


def test_fcfs_equal_arrival_times_tie_breaking():
    """FCFS with identical arrival times breaks ties by job_id."""
    jobs = [
        JobScheduleItem(job_id="JOB-B", arrival_time=0.0, burst_time=3.0, priority=1),
        JobScheduleItem(job_id="JOB-A", arrival_time=0.0, burst_time=2.0, priority=1),
    ]
    result = schedule_fcfs(jobs)
    assert [j.job_id for j in result.jobs] == ["JOB-A", "JOB-B"]


def test_fcfs_idle_time_gap():
    """FCFS advances clock when CPU is idle waiting for arrival."""
    jobs = [
        JobScheduleItem(job_id="J1", arrival_time=1.0, burst_time=2.0, priority=1),
        JobScheduleItem(job_id="J2", arrival_time=10.0, burst_time=3.0, priority=1),
    ]
    result = schedule_fcfs(jobs)
    j1, j2 = result.jobs
    assert j1.start_time == 1.0 and j1.completion_time == 3.0
    assert j2.start_time == 10.0 and j2.completion_time == 13.0
    assert j2.waiting_time == 0.0


# ====================================================================
# SJF Tests
# ====================================================================

def test_sjf_different_burst_times_equal_arrival():
    """SJF orders strictly by burst time when all jobs are available at t=0."""
    jobs = [
        JobScheduleItem(job_id="J1", arrival_time=0.0, burst_time=8.0),
        JobScheduleItem(job_id="J2", arrival_time=0.0, burst_time=3.0),
        JobScheduleItem(job_id="J3", arrival_time=0.0, burst_time=5.0),
    ]
    result = schedule_sjf(jobs)

    # Order should be J2 (3) -> J3 (5) -> J1 (8)
    assert [j.job_id for j in result.jobs] == ["J2", "J3", "J1"]
    j2, j3, j1 = result.jobs
    assert (j2.start_time, j2.completion_time) == (0.0, 3.0)
    assert (j3.start_time, j3.completion_time) == (3.0, 8.0)
    assert (j1.start_time, j1.completion_time) == (8.0, 16.0)

    # J2 WT=0, J3 WT=3, J1 WT=8 -> Avg WT = 11/3 = 3.67
    assert result.average_waiting_time == pytest.approx(3.67, 0.01)


def test_sjf_different_arrival_times():
    """
    SJF dynamic ready queue:
    J1 arrives at 0 with burst 6. Starts at 0, finishes at 6.
    During [0, 6], J2 (AT=2, BT=8) and J3 (AT=3, BT=2) arrive.
    At t=6, ready pool contains J2 (BT=8) and J3 (BT=2).
    SJF must choose J3 before J2!
    """
    jobs = [
        JobScheduleItem(job_id="J1", arrival_time=0.0, burst_time=6.0),
        JobScheduleItem(job_id="J2", arrival_time=2.0, burst_time=8.0),
        JobScheduleItem(job_id="J3", arrival_time=3.0, burst_time=2.0),
    ]
    result = schedule_sjf(jobs)

    assert [j.job_id for j in result.jobs] == ["J1", "J3", "J2"]
    j1, j3, j2 = result.jobs
    assert (j1.start_time, j1.completion_time) == (0.0, 6.0)
    assert (j3.start_time, j3.completion_time) == (6.0, 8.0)
    assert (j2.start_time, j2.completion_time) == (8.0, 16.0)
    assert j3.waiting_time == 6.0 - 3.0 == 3.0
    assert j2.waiting_time == 8.0 - 2.0 == 6.0


def test_sjf_tie_breaking():
    """SJF with same burst times breaks ties by earlier arrival, then job_id."""
    jobs = [
        JobScheduleItem(job_id="J-LATE", arrival_time=2.0, burst_time=4.0),
        JobScheduleItem(job_id="J-EARLY", arrival_time=0.0, burst_time=4.0),
    ]
    result = schedule_sjf(jobs)
    assert [j.job_id for j in result.jobs] == ["J-EARLY", "J-LATE"]


# ====================================================================
# Round Robin Tests
# ====================================================================

def test_round_robin_basic_quantum():
    """
    Round Robin with quantum = 2.
    J1: AT=0, BT=5
    J2: AT=0, BT=3
    J3: AT=0, BT=1

    Slices:
    [0, 2]: J1 (rem 3)
    [2, 4]: J2 (rem 1)
    [4, 5]: J3 (rem 0, finishes at 5)
    [5, 7]: J1 (rem 1)
    [7, 8]: J2 (rem 0, finishes at 8)
    [8, 9]: J1 (rem 0, finishes at 9)
    """
    jobs = [
        JobScheduleItem(job_id="J1", arrival_time=0.0, burst_time=5.0),
        JobScheduleItem(job_id="J2", arrival_time=0.0, burst_time=3.0),
        JobScheduleItem(job_id="J3", arrival_time=0.0, burst_time=1.0),
    ]
    result = schedule_round_robin(jobs, quantum=2.0)

    assert result.total_jobs == 3
    job_map = {j.job_id: j for j in result.jobs}

    assert job_map["J3"].completion_time == 5.0
    assert job_map["J2"].completion_time == 8.0
    assert job_map["J1"].completion_time == 9.0

    # Response times:
    assert job_map["J1"].response_time == 0.0
    assert job_map["J2"].response_time == 2.0
    assert job_map["J3"].response_time == 4.0

    # Turnaround times: CT - AT
    assert job_map["J1"].turnaround_time == 9.0
    assert job_map["J2"].turnaround_time == 8.0
    assert job_map["J3"].turnaround_time == 5.0

    # Waiting times: TAT - BT
    assert job_map["J1"].waiting_time == 9.0 - 5.0 == 4.0
    assert job_map["J2"].waiting_time == 8.0 - 3.0 == 5.0
    assert job_map["J3"].waiting_time == 5.0 - 1.0 == 4.0

    assert len(result.execution_slices) == 6


def test_round_robin_quantum_larger_than_burst():
    """When quantum >= max burst time, RR behaves like FCFS."""
    jobs = [
        JobScheduleItem(job_id="J1", arrival_time=0.0, burst_time=2.0),
        JobScheduleItem(job_id="J2", arrival_time=0.0, burst_time=3.0),
    ]
    result_rr = schedule_round_robin(jobs, quantum=10.0)
    result_fcfs = schedule_fcfs(jobs)

    assert result_rr.average_waiting_time == result_fcfs.average_waiting_time
    assert result_rr.average_turnaround_time == result_fcfs.average_turnaround_time


def test_round_robin_quantum_one():
    """Round Robin with quantum=1.0 runs fine-grained cycles."""
    jobs = [
        JobScheduleItem(job_id="J1", arrival_time=0.0, burst_time=2.0),
        JobScheduleItem(job_id="J2", arrival_time=0.0, burst_time=2.0),
    ]
    result = schedule_round_robin(jobs, quantum=1.0)
    slice_jobs = [s.job_id for s in result.execution_slices]
    assert slice_jobs == ["J1", "J2", "J1", "J2"]


def test_round_robin_invalid_quantum():
    """Quantum <= 0 should raise ValueError."""
    jobs = [JobScheduleItem(job_id="J1", arrival_time=0.0, burst_time=2.0)]
    with pytest.raises(ValueError):
        schedule_round_robin(jobs, quantum=0.0)


# ====================================================================
# Priority Tests
# ====================================================================

def test_priority_scheduling_basic():
    """
    Priority Scheduling: lower numerical value = higher priority.
    P1 (Priority 3, BT=4)
    P2 (Priority 1, BT=2) -> runs first!
    P3 (Priority 2, BT=3) -> runs second!
    """
    jobs = [
        JobScheduleItem(job_id="P1", arrival_time=0.0, burst_time=4.0, priority=3),
        JobScheduleItem(job_id="P2", arrival_time=0.0, burst_time=2.0, priority=1),
        JobScheduleItem(job_id="P3", arrival_time=0.0, burst_time=3.0, priority=2),
    ]
    result = schedule_priority(jobs)

    assert [j.job_id for j in result.jobs] == ["P2", "P3", "P1"]
    p2, p3, p1 = result.jobs
    assert (p2.start_time, p2.completion_time) == (0.0, 2.0)
    assert (p3.start_time, p3.completion_time) == (2.0, 5.0)
    assert (p1.start_time, p1.completion_time) == (5.0, 9.0)


def test_priority_tie_breaking():
    """
    Priority tie-breaking:
    1. Lower priority value
    2. Earlier arrival time
    3. Lower job_id
    """
    jobs = [
        JobScheduleItem(job_id="J2", arrival_time=2.0, burst_time=3.0, priority=1),
        JobScheduleItem(job_id="J1", arrival_time=0.0, burst_time=3.0, priority=1),
    ]
    result = schedule_priority(jobs)
    assert [j.job_id for j in result.jobs] == ["J1", "J2"]


def test_priority_different_arrival_times():
    """
    Non-preemptive priority:
    J1 arrives at 0 (prio 5, BT=4). Starts at 0.
    J2 arrives at 1 (prio 1, BT=2). High priority, but must wait until J1 completes at 4!
    """
    jobs = [
        JobScheduleItem(job_id="J1", arrival_time=0.0, burst_time=4.0, priority=5),
        JobScheduleItem(job_id="J2", arrival_time=1.0, burst_time=2.0, priority=1),
    ]
    result = schedule_priority(jobs)
    assert [j.job_id for j in result.jobs] == ["J1", "J2"]
    j1, j2 = result.jobs
    assert (j1.start_time, j1.completion_time) == (0.0, 4.0)
    assert (j2.start_time, j2.completion_time) == (4.0, 6.0)
    assert j2.waiting_time == 3.0


# ====================================================================
# Manager & Comparison Tests
# ====================================================================

def test_scheduler_manager_dispatch():
    """SchedulerManager dispatches to all supported algorithms."""
    jobs = [
        {"job_id": "1", "arrival_time": 0.0, "burst_time": 4.0, "priority": 1},
        {"job_id": "2", "arrival_time": 1.0, "burst_time": 2.0, "priority": 2},
    ]

    for algo in ["FCFS", "SJF", "ROUND_ROBIN", "RR", "PRIORITY"]:
        res = SchedulerManager.schedule(jobs, algorithm=algo, quantum=2.0)
        assert res.total_jobs == 2
        assert len(res.jobs) == 2
        assert res.average_waiting_time >= 0.0


def test_scheduler_manager_compare_algorithms():
    """SchedulerManager.compare_algorithms evaluates all 4 algorithms on identical data."""
    jobs = [
        {"job_id": "101", "arrival_time": 0.0, "burst_time": 5.0, "priority": 2},
        {"job_id": "102", "arrival_time": 1.0, "burst_time": 2.0, "priority": 1},
        {"job_id": "103", "arrival_time": 2.0, "burst_time": 8.0, "priority": 3},
        {"job_id": "104", "arrival_time": 3.0, "burst_time": 3.0, "priority": 2},
    ]
    comparison = SchedulerManager.compare_algorithms(jobs, quantum=2.0)

    assert comparison["total_jobs"] == 4
    assert len(comparison["comparison_table"]) == 4
    algo_names = [row["algorithm"] for row in comparison["comparison_table"]]
    assert set(algo_names) == {"FCFS", "SJF", "ROUND_ROBIN", "PRIORITY"}
    assert comparison["recommended_algorithm"] in algo_names

    # Check metrics are populated and realistic
    for row in comparison["comparison_table"]:
        assert row["average_waiting_time"] >= 0.0
        assert row["average_turnaround_time"] >= 0.0
        assert row["average_response_time"] >= 0.0
