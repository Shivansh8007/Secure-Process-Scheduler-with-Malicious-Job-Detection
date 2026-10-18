from fastapi import status


def test_worker_start_and_result_success(client):
    """Test full worker execution flow: Submit -> Schedule -> Start (RUNNING) -> Result (COMPLETED)."""
    # 1. Submit
    create_res = client.post("/jobs", json={"command": "python test.py", "burst_time": 5.0, "priority": 2})
    job_id = create_res.json()["job_id"]

    # 2. Schedule
    sched_res = client.post("/jobs/schedule", json={"algorithm": "FCFS", "job_ids": [job_id]})
    assert sched_res.status_code == status.HTTP_200_OK

    # 3. Worker Starts Job
    start_res = client.patch(f"/jobs/{job_id}/start", json={"worker_id": "worker-1"})
    assert start_res.status_code == status.HTTP_200_OK
    assert start_res.json()["status"] == "RUNNING"
    assert start_res.json()["started_at"] is not None

    # 4. Worker Reports Execution Result
    result_payload = {
        "worker_id": "worker-1",
        "status": "COMPLETED",
        "output": "Process finished successfully with exit code 0",
        "error_message": None,
        "execution_time": 2.31
    }
    result_res = client.post(f"/jobs/{job_id}/result", json=result_payload)
    assert result_res.status_code == status.HTTP_200_OK
    
    data = result_res.json()
    assert data["job_id"] == job_id
    assert data["status"] == "COMPLETED"
    assert data["worker_id"] == "worker-1"
    assert data["execution_time"] == 2.31

    # Verify job record updated in database
    job_res = client.get(f"/jobs/{job_id}")
    assert job_res.json()["status"] == "COMPLETED"
    assert job_res.json()["completed_at"] is not None


def test_worker_start_unscheduled_job_rejected(client):
    """Ensure worker cannot start a job that has not been SCHEDULED yet (e.g. still PENDING)."""
    create_res = client.post("/jobs", json={"command": "raw.py", "burst_time": 1.0})
    job_id = create_res.json()["job_id"]

    # Attempt to start directly while still PENDING
    start_res = client.patch(f"/jobs/{job_id}/start", json={"worker_id": "worker-1"})
    assert start_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid lifecycle transition" in start_res.json()["detail"]


def test_worker_reports_failure(client):
    """Test worker reporting an execution failure (status = FAILED)."""
    create_res = client.post("/jobs", json={"command": "broken.py", "burst_time": 2.0})
    job_id = create_res.json()["job_id"]

    client.post("/jobs/schedule", json={"algorithm": "FCFS", "job_ids": [job_id]})
    client.patch(f"/jobs/{job_id}/start", json={"worker_id": "worker-2"})

    result_payload = {
        "worker_id": "worker-2",
        "status": "FAILED",
        "output": "",
        "error_message": "FileNotFoundError: No such file broken.py",
        "execution_time": 0.45
    }
    result_res = client.post(f"/jobs/{job_id}/result", json=result_payload)
    assert result_res.status_code == status.HTTP_200_OK
    assert result_res.json()["status"] == "FAILED"

    # Verify job status in database is FAILED
    job_data = client.get(f"/jobs/{job_id}").json()
    assert job_data["status"] == "FAILED"


def test_worker_result_nonexistent_job_returns_404(client):
    """Verify posting a result for an unknown job returns 404."""
    result_payload = {
        "worker_id": "worker-1",
        "status": "COMPLETED",
        "output": "test",
        "execution_time": 1.0
    }
    response = client.post("/jobs/999999/result", json=result_payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND
