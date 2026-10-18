from fastapi import status


def test_execution_history_and_audit_logging(client):
    """Verify execution history records and audit logs are properly stored and queryable."""
    # 1. Create Job
    create_res = client.post("/jobs", json={"command": "python test.py", "burst_time": 5.0, "priority": 2})
    job_id = create_res.json()["job_id"]

    # 2. Schedule
    client.post("/jobs/schedule", json={"algorithm": "FCFS", "job_ids": [job_id]})

    # 3. Start
    client.patch(f"/jobs/{job_id}/start", json={"worker_id": "worker-alpha"})

    # 4. Result
    client.post(f"/jobs/{job_id}/result", json={
        "worker_id": "worker-alpha",
        "status": "COMPLETED",
        "output": "Execution output data here",
        "error_message": None,
        "execution_time": 1.75
    })

    # 5. Query execution history for this job
    hist_res = client.get(f"/jobs/{job_id}/history")
    assert hist_res.status_code == status.HTTP_200_OK
    hist_data = hist_res.json()
    assert len(hist_data) >= 1
    record = hist_data[0]
    assert record["job_id"] == job_id
    assert record["worker_id"] == "worker-alpha"
    assert record["status"] == "COMPLETED"
    assert record["output"] == "Execution output data here"
    assert record["execution_time"] == 1.75
    assert record["started_at"] is not None
    assert record["completed_at"] is not None

    # 6. Query global history endpoint
    global_hist = client.get("/history")
    assert global_hist.status_code == status.HTTP_200_OK
    assert any(h["job_id"] == job_id for h in global_hist.json())

    # 7. Query audit logs for this job
    audit_res = client.get(f"/jobs/{job_id}/audit-logs")
    assert audit_res.status_code == status.HTTP_200_OK
    audit_data = audit_res.json()
    events = [entry["event_type"] for entry in audit_data]

    # Verify lifecycle audit trail
    assert "JOB_CREATED" in events
    assert "JOB_SCHEDULED" in events
    assert "JOB_STARTED" in events
    assert "JOB_COMPLETED" in events
