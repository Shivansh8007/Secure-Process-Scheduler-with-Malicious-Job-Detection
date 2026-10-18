from fastapi import status


def test_schedule_fcfs(client):
    """Test FCFS scheduling: orders primarily by arrival_time."""
    # Submit 3 jobs with known arrival times
    j1 = client.post("/jobs", json={"command": "task1", "burst_time": 5.0, "arrival_time": 10.0}).json()["job_id"]
    j2 = client.post("/jobs", json={"command": "task2", "burst_time": 2.0, "arrival_time": 5.0}).json()["job_id"]
    j3 = client.post("/jobs", json={"command": "task3", "burst_time": 8.0, "arrival_time": 8.0}).json()["job_id"]

    response = client.post("/jobs/schedule", json={"algorithm": "FCFS"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["algorithm"] == "FCFS"
    assert data["total_scheduled"] >= 3

    # Under FCFS, arrival times are 5.0 (j2), 8.0 (j3), 10.0 (j1)
    orders = {item["job_id"]: item["execution_order"] for item in data["schedule"]}
    assert orders[j2] < orders[j3] < orders[j1]

    # Verify that j1's stored status is now SCHEDULED and algorithm is recorded
    job1_data = client.get(f"/jobs/{j1}").json()
    assert job1_data["status"] == "SCHEDULED"
    assert job1_data["algorithm"] == "FCFS"


def test_schedule_sjf(client):
    """Test SJF scheduling: orders primarily by shortest burst_time."""
    j_long = client.post("/jobs", json={"command": "long", "burst_time": 20.0, "arrival_time": 1.0}).json()["job_id"]
    j_short = client.post("/jobs", json={"command": "short", "burst_time": 2.0, "arrival_time": 2.0}).json()["job_id"]

    response = client.post("/jobs/schedule", json={
        "algorithm": "SJF",
        "job_ids": [j_long, j_short]
    })
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    orders = {item["job_id"]: item["execution_order"] for item in data["schedule"]}
    assert orders[j_short] < orders[j_long]


def test_schedule_priority(client):
    """Test Priority scheduling: orders primarily by priority (lower number = higher priority)."""
    j_low_prio = client.post("/jobs", json={"command": "low", "burst_time": 5.0, "priority": 5, "arrival_time": 1.0}).json()["job_id"]
    j_high_prio = client.post("/jobs", json={"command": "high", "burst_time": 5.0, "priority": 1, "arrival_time": 2.0}).json()["job_id"]

    response = client.post("/jobs/schedule", json={
        "algorithm": "PRIORITY",
        "job_ids": [j_low_prio, j_high_prio]
    })
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    orders = {item["job_id"]: item["execution_order"] for item in data["schedule"]}
    assert orders[j_high_prio] < orders[j_low_prio]


def test_scheduler_input_contract(client):
    """Verify GET /jobs/schedule/input matches Member 2's expected data contract."""
    client.post("/jobs", json={"command": "test", "burst_time": 3.0, "priority": 1})
    response = client.get("/jobs/schedule/input")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "job_id" in first
        assert "arrival_time" in first
        assert "burst_time" in first
        assert "priority" in first
        assert "status" in first


def test_invalid_algorithm_rejected(client):
    """Verify submitting an unsupported algorithm name returns 422."""
    response = client.post("/jobs/schedule", json={"algorithm": "RANDOM_GUESS"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_compare_algorithms_process_breakdown(client):
    """Verify GET /jobs/schedule/compare returns per-process metrics and Gantt charts."""
    client.post("/jobs", json={"command": "task1", "arrival_time": 0.0, "burst_time": 4.0, "priority": 2})
    client.post("/jobs", json={"command": "task2", "arrival_time": 1.0, "burst_time": 2.0, "priority": 1})

    res = client.get("/jobs/schedule/compare?quantum=2.0")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["total_jobs"] >= 2
    assert "comparison_table" in data
    assert "process_comparison" in data
    assert len(data["process_comparison"]) >= 2

    # Check that each process contains metrics for all 4 algorithms
    first_proc = data["process_comparison"][0]
    assert "job_id" in first_proc
    assert "algorithms" in first_proc
    for algo in ["FCFS", "SJF", "ROUND_ROBIN", "PRIORITY"]:
        assert algo in first_proc["algorithms"]
        m = first_proc["algorithms"][algo]
        assert "order" in m
        assert "waiting_time" in m
        assert "turnaround_time" in m

    # Check Gantt charts
    assert "gantt_charts" in data
    assert "ROUND_ROBIN" in data["gantt_charts"]
    assert len(data["gantt_charts"]["ROUND_ROBIN"]) > 0


def test_custom_process_comparison(client):
    """Verify POST /jobs/schedule/compare/custom evaluates custom process payloads."""
    payload = {
        "quantum": 2.0,
        "processes": [
            {"job_id": "P1", "arrival_time": 0.0, "burst_time": 6.0, "priority": 3, "command": "cmd1"},
            {"job_id": "P2", "arrival_time": 1.0, "burst_time": 3.0, "priority": 1, "command": "cmd2"},
            {"job_id": "P3", "arrival_time": 2.0, "burst_time": 1.0, "priority": 2, "command": "cmd3"},
        ]
    }
    res = client.post("/jobs/schedule/compare/custom", json=payload)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["total_jobs"] == 3
    assert len(data["comparison_table"]) == 4
    assert len(data["process_comparison"]) == 3
    assert data["recommended_algorithm"] in ["FCFS", "SJF", "ROUND_ROBIN", "PRIORITY"]

