from fastapi import status


def test_submit_job_defaults(client):
    """Test standard job submission with automatic job_id and arrival_time."""
    payload = {
        "command": "python test.py",
        "burst_time": 5.0,
        "priority": 2
    }
    response = client.post("/jobs", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"
    assert data["message"] == "Job submitted successfully"
    assert data["job"]["command"] == "python test.py"
    assert data["job"]["burst_time"] == 5.0
    assert data["job"]["priority"] == 2
    assert data["job"]["arrival_time"] > 0
    assert data["job"]["status"] == "PENDING"


def test_submit_job_explicit_id_and_arrival(client):
    """Test job submission with client-provided job_id and arrival_time."""
    payload = {
        "job_id": "105",
        "command": "echo 'Hello JobSentinel'",
        "burst_time": 2.5,
        "priority": 1,
        "arrival_time": 10.0
    }
    response = client.post("/jobs", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    
    data = response.json()
    assert str(data["job_id"]) == "105"
    assert data["job"]["arrival_time"] == 10.0


def test_duplicate_job_id_rejected(client):
    """Ensure submitting a job with duplicate job_id returns 409 Conflict."""
    payload = {
        "job_id": "200",
        "command": "ls -la",
        "burst_time": 3.0,
        "priority": 1
    }
    res1 = client.post("/jobs", json=payload)
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = client.post("/jobs", json=payload)
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in res2.json()["detail"]


def test_get_job_by_id(client):
    """Verify retrieving a job by its unique job_id."""
    res_create = client.post("/jobs", json={"command": "task.py", "burst_time": 4.0, "priority": 1})
    job_id = res_create.json()["job_id"]

    res_get = client.get(f"/jobs/{job_id}")
    assert res_get.status_code == status.HTTP_200_OK
    assert res_get.json()["job_id"] == job_id
    assert res_get.json()["status"] == "PENDING"


def test_get_nonexistent_job_returns_404(client):
    """Verify querying an unknown job_id yields 404 Not Found."""
    response = client.get("/jobs/999999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_list_pending_jobs(client):
    """Verify GET /jobs/pending returns all pending jobs ordered by arrival time."""
    client.post("/jobs", json={"command": "job_late.py", "burst_time": 2.0, "arrival_time": 50.0})
    client.post("/jobs", json={"command": "job_early.py", "burst_time": 3.0, "arrival_time": 10.0})

    response = client.get("/jobs/pending")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) >= 2

    # Verify order by arrival_time
    arrival_times = [j["arrival_time"] for j in data]
    assert arrival_times == sorted(arrival_times)
