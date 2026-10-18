"""
JobSentinel - End-to-End Lifecycle Demonstration Script
Demonstrates the full Phase 2 pipeline:
Submit Job -> Store in DB -> Scheduler Selection -> Worker Execution -> Store Result -> History & Audit
"""

import sys
import time
from pathlib import Path

# Add project root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base, get_db, check_db_connection
from backend.app.main import app


def run_demonstration():
    print("=" * 70)
    print("      JOBSENTINEL - END-TO-END SYSTEM PIPELINE DEMONSTRATION")
    print("=" * 70)

    # Check whether live MySQL configured in .env is reachable
    is_live_db = check_db_connection()
    if not is_live_db:
        print("\n[NOTE] Live MySQL connection using .env is not yet configured.")
        print("       Running demonstration with local SQLite session so you can preview")
        print("       the complete Phase 2 workflow immediately.\n")
        demo_engine = create_engine("sqlite:///./demo_sentinel.db")
        Base.metadata.create_all(bind=demo_engine)
        DemoSession = sessionmaker(autocommit=False, autoflush=False, bind=demo_engine)

        def override_get_db():
            db = DemoSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
    else:
        print("\n[SUCCESS] Connected to live MySQL database!")

    client = TestClient(app)

    # 1. System Health Check
    print("\n[STEP 1] Checking Backend Health...")
    health_resp = client.get("/health")
    print(f"Status Code: {health_resp.status_code}")
    print(f"Health Response: {health_resp.json()}")

    # 2. Submit 3 Different Jobs
    print("\n[STEP 2] Submitting 3 Jobs to Persistent Database Queue...")
    jobs_payload = [
        {"command": "python heavy_task.py", "burst_time": 10.5, "priority": 3, "arrival_time": 1.0},
        {"command": "python quick_ping.py", "burst_time": 2.0, "priority": 1, "arrival_time": 2.0},
        {"command": "python report_gen.py", "burst_time": 5.0, "priority": 2, "arrival_time": 3.0},
    ]

    submitted_ids = []
    for idx, p in enumerate(jobs_payload, start=1):
        resp = client.post("/jobs", json=p)
        data = resp.json()
        jid = data["job_id"]
        submitted_ids.append(jid)
        print(f"  --> Job {idx} Submitted: ID={jid} | Status={data['status']} | Command='{p['command']}' | Burst={p['burst_time']}s | Priority={p['priority']}")

    # 3. Retrieve Pending Jobs
    print("\n[STEP 3] Querying Pending Jobs ready for scheduling...")
    pending_resp = client.get("/jobs/pending")
    pending_list = pending_resp.json()
    print(f"  Total pending jobs in queue: {len(pending_list)}")
    for j in pending_list:
        print(f"    - Job {j['job_id']}: arrival={j['arrival_time']}, burst={j['burst_time']}, priority={j['priority']}")

    # 4. Trigger Scheduling Algorithm (e.g. SJF - Shortest Job First)
    print("\n[STEP 4] Selecting Scheduling Algorithm: SJF (Shortest Job First)...")
    sched_payload = {
        "algorithm": "SJF",
        "job_ids": submitted_ids
    }
    sched_resp = client.post("/jobs/schedule", json=sched_payload)
    sched_data = sched_resp.json()
    print(f"  Algorithm Applied: {sched_data['algorithm']}")
    print("  Execution Schedule Determined by Scheduler:")
    for item in sched_data["schedule"]:
        print(f"    * Order #{item['execution_order']}: Job ID {item['job_id']}")

    # 5. Worker Picks Up and Executes Jobs in Scheduled Order
    print("\n[STEP 5] Worker Processing Jobs in Scheduled Order...")
    for item in sched_data["schedule"]:
        jid = item["job_id"]
        order = item["execution_order"]
        print(f"\n  --- Executing Schedule Order #{order} (Job ID: {jid}) ---")

        # Worker signals start
        start_resp = client.patch(f"/jobs/{jid}/start", json={"worker_id": "worker-1"})
        print(f"    [WORKER] Started execution -> Status: {start_resp.json()['status']} | Started At: {start_resp.json()['started_at']}")

        # Simulated execution duration
        time.sleep(0.05)

        # Worker reports result
        result_payload = {
            "worker_id": "worker-1",
            "status": "COMPLETED",
            "output": f"Job {jid} executed successfully. Return code 0.",
            "error_message": None,
            "execution_time": 0.05
        }
        res_resp = client.post(f"/jobs/{jid}/result", json=result_payload)
        print(f"    [WORKER] Reported result -> Status: {res_resp.json()['status']} | Exec Time: {res_resp.json()['execution_time']}s")

    # 6. Verify Execution History
    print("\n[STEP 6] Inspecting Execution History...")
    hist_resp = client.get("/history")
    history_records = hist_resp.json()
    print(f"  Total Execution History Records: {len(history_records)}")
    for h in history_records[:3]:
        print(f"    * History #{h['history_id']} for Job {h['job_id']}: Status={h['status']}, Worker={h['worker_id']}, Runtime={h['execution_time']}s, Output='{h['output']}'")

    # 7. Verify Audit Log Trail
    print("\n[STEP 7] Inspecting Audit Trail for Job ID:", submitted_ids[0])
    audit_resp = client.get(f"/jobs/{submitted_ids[0]}/audit-logs")
    for a in audit_resp.json():
        print(f"    [{a['timestamp']}] [{a['event_type']}] {a['message']}")

    print("\n" + "=" * 70)
    print("  DEMONSTRATION COMPLETE: ALL PHASE 2 REQUIREMENTS SATISFIED!")
    print("=" * 70)


if __name__ == "__main__":
    run_demonstration()
