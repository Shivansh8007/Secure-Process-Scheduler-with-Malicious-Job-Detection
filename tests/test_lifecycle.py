from fastapi import status


def test_valid_lifecycle_step_by_step(client):
    """Test standard lifecycle transition: PENDING -> SCHEDULED."""
    res_create = client.post("/jobs", json={"command": "task.py", "burst_time": 4.0, "priority": 1})
    job_id = res_create.json()["job_id"]

    # Transition PENDING -> SCHEDULED
    res_status = client.patch(f"/jobs/{job_id}/status", json={"status": "SCHEDULED"})
    assert res_status.status_code == status.HTTP_200_OK
    assert res_status.json()["status"] == "SCHEDULED"

    # Transition SCHEDULED -> RUNNING
    res_running = client.patch(f"/jobs/{job_id}/status", json={"status": "RUNNING"})
    assert res_running.status_code == status.HTTP_200_OK
    assert res_running.json()["status"] == "RUNNING"

    # Transition RUNNING -> COMPLETED
    res_completed = client.patch(f"/jobs/{job_id}/status", json={"status": "COMPLETED"})
    assert res_completed.status_code == status.HTTP_200_OK
    assert res_completed.json()["status"] == "COMPLETED"


def test_invalid_lifecycle_transition_rejected(client):
    """Test that direct transition from PENDING to RUNNING or COMPLETED is strictly rejected."""
    res_create = client.post("/jobs", json={"command": "task.py", "burst_time": 4.0, "priority": 1})
    job_id = res_create.json()["job_id"]

    # Try skipping SCHEDULED: PENDING -> RUNNING
    res_invalid = client.patch(f"/jobs/{job_id}/status", json={"status": "RUNNING"})
    assert res_invalid.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid lifecycle transition" in res_invalid.json()["detail"]

    # Try PENDING -> COMPLETED directly
    res_invalid2 = client.patch(f"/jobs/{job_id}/status", json={"status": "COMPLETED"})
    assert res_invalid2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_completed_job_cannot_be_reopened(client):
    """Ensure completed jobs cannot transition to any other status."""
    res_create = client.post("/jobs", json={"command": "task.py", "burst_time": 4.0, "priority": 1})
    job_id = res_create.json()["job_id"]

    client.patch(f"/jobs/{job_id}/status", json={"status": "SCHEDULED"})
    client.patch(f"/jobs/{job_id}/status", json={"status": "RUNNING"})
    client.patch(f"/jobs/{job_id}/status", json={"status": "COMPLETED"})

    # Try modifying completed job back to RUNNING
    res_reopen = client.patch(f"/jobs/{job_id}/status", json={"status": "RUNNING"})
    assert res_reopen.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
