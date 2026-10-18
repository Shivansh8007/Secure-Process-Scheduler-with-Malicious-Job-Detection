"""
Integration Tests for JobSentinel Phase 2 Pipeline
Validates end-to-end flow:
Submit Job -> Store in DB -> Select Algorithm -> Scheduler -> Worker Execution -> Store Result -> History & Audit
"""

from fastapi import status


def test_end_to_end_fcfs_pipeline(client):
    """
    Full end-to-end pipeline test with FCFS:
    1. Submit 3 jobs
    2. Retrieve pending jobs
    3. Trigger scheduling with execute_jobs=True
    4. Worker executes jobs
    5. Database updates jobs to COMPLETED
    6. History is recorded
    7. Audit trail is logged
    """
    # 1. Submit 3 jobs with simple executable Python tasks
    j1 = client.post("/jobs", json={
        "command": "print('Output from Job 1')",
        "burst_time": 4.0,
        "priority": 2,
        "arrival_time": 1.0
    }).json()["job_id"]

    j2 = client.post("/jobs", json={
        "command": "print('Output from Job 2')",
        "burst_time": 2.0,
        "priority": 1,
        "arrival_time": 2.0
    }).json()["job_id"]

    j3 = client.post("/jobs", json={
        "command": "print('Output from Job 3')",
        "burst_time": 3.0,
        "priority": 3,
        "arrival_time": 3.0
    }).json()["job_id"]

    # 2. Verify all are in PENDING queue
    pending_res = client.get("/jobs/pending")
    assert pending_res.status_code == status.HTTP_200_OK
    pending_ids = [j["job_id"] for j in pending_res.json()]
    assert set([j1, j2, j3]).issubset(set(pending_ids))

    # 3. Schedule and execute via FCFS
    sched_res = client.post("/jobs/schedule", json={
        "algorithm": "FCFS",
        "job_ids": [j1, j2, j3],
        "execute_jobs": True,
        "worker_id": "worker-demo-1"
    })
    assert sched_res.status_code == status.HTTP_200_OK
    data = sched_res.json()

    assert data["algorithm"] == "FCFS"
    assert data["total_scheduled"] == 3
    assert data["average_waiting_time"] is not None
    assert data["average_turnaround_time"] is not None
    assert data["average_response_time"] is not None

    # Check execution order (FCFS by arrival: j1 -> j2 -> j3)
    order_map = {item["job_id"]: item["execution_order"] for item in data["schedule"]}
    assert order_map[j1] == 1
    assert order_map[j2] == 2
    assert order_map[j3] == 3

    # Check worker results
    assert data["executed_results"] is not None
    assert len(data["executed_results"]) == 3
    for res in data["executed_results"]:
        assert res["status"] == "COMPLETED"
        assert "Output from Job" in res["output"]

    # 4. Verify DB status of each job is COMPLETED
    for jid in [j1, j2, j3]:
        job_db = client.get(f"/jobs/{jid}").json()
        assert job_db["status"] == "COMPLETED"
        assert job_db["started_at"] is not None
        assert job_db["completed_at"] is not None

    # 5. Verify execution history
    hist_res = client.get("/history")
    assert hist_res.status_code == status.HTTP_200_OK
    history = hist_res.json()
    hist_jids = [h["job_id"] for h in history]
    assert j1 in hist_jids and j2 in hist_jids and j3 in hist_jids

    # 6. Verify audit trail for j1
    audit_res = client.get(f"/jobs/{j1}/audit-logs")
    assert audit_res.status_code == status.HTTP_200_OK
    events = [a["event_type"] for a in audit_res.json()]
    assert "JOB_CREATED" in events
    assert "JOB_SCHEDULED" in events
    assert "JOB_STARTED" in events
    assert "JOB_COMPLETED" in events


def test_end_to_end_sjf_pipeline(client):
    """Test SJF end-to-end: executes shortest burst first."""
    j_long = client.post("/jobs", json={
        "command": "print('Long')",
        "burst_time": 9.0,
        "priority": 1,
        "arrival_time": 0.0
    }).json()["job_id"]

    j_short = client.post("/jobs", json={
        "command": "print('Short')",
        "burst_time": 1.0,
        "priority": 1,
        "arrival_time": 0.0
    }).json()["job_id"]

    sched_res = client.post("/jobs/schedule", json={
        "algorithm": "SJF",
        "job_ids": [j_long, j_short],
        "execute_jobs": True
    })
    assert sched_res.status_code == status.HTTP_200_OK
    data = sched_res.json()
    order_map = {item["job_id"]: item["execution_order"] for item in data["schedule"]}
    assert order_map[j_short] < order_map[j_long]


def test_end_to_end_priority_pipeline(client):
    """Test Priority end-to-end: executes highest priority (lowest number) first."""
    j_low = client.post("/jobs", json={
        "command": "print('Low prio')",
        "burst_time": 2.0,
        "priority": 5,
        "arrival_time": 0.0
    }).json()["job_id"]

    j_high = client.post("/jobs", json={
        "command": "print('High prio')",
        "burst_time": 2.0,
        "priority": 1,
        "arrival_time": 0.0
    }).json()["job_id"]

    sched_res = client.post("/jobs/schedule", json={
        "algorithm": "PRIORITY",
        "job_ids": [j_low, j_high],
        "execute_jobs": True
    })
    assert sched_res.status_code == status.HTTP_200_OK
    data = sched_res.json()
    order_map = {item["job_id"]: item["execution_order"] for item in data["schedule"]}
    assert order_map[j_high] < order_map[j_low]


def test_worker_failure_handling(client):
    """Test worker executing a failing script transitions to FAILED."""
    failing_job = client.post("/jobs", json={
        "command": "raise ValueError('Intentional Worker Task Failure')",
        "burst_time": 1.0,
        "priority": 1
    }).json()["job_id"]

    sched_res = client.post("/jobs/schedule", json={
        "algorithm": "FCFS",
        "job_ids": [failing_job],
        "execute_jobs": True
    })
    assert sched_res.status_code == status.HTTP_200_OK

    job_db = client.get(f"/jobs/{failing_job}").json()
    assert job_db["status"] == "FAILED"

    # History should preserve error
    hist = client.get(f"/jobs/{failing_job}/history").json()
    assert len(hist) > 0
    assert hist[0]["status"] == "FAILED"
    assert "ValueError" in (hist[0]["error_message"] or "")


def test_algorithm_comparison_api(client):
    """Test GET /jobs/schedule/compare endpoint."""
    client.post("/jobs", json={"command": "print(1)", "burst_time": 5.0, "priority": 2, "arrival_time": 0.0})
    client.post("/jobs", json={"command": "print(2)", "burst_time": 2.0, "priority": 1, "arrival_time": 1.0})

    compare_res = client.get("/jobs/schedule/compare?quantum=2.0")
    assert compare_res.status_code == status.HTTP_200_OK
    data = compare_res.json()

    assert data["total_jobs"] >= 2
    assert len(data["comparison_table"]) == 4
    assert data["recommended_algorithm"] in ["FCFS", "SJF", "ROUND_ROBIN", "PRIORITY"]


def test_dashboard_stats_api(client):
    """Test GET /dashboard/stats for frontend compatibility."""
    stats_res = client.get("/dashboard/stats")
    assert stats_res.status_code == status.HTTP_200_OK
    data = stats_res.json()
    assert "total" in data
    assert "pending" in data
    assert "completed" in data
    assert "failed" in data
