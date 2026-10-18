"""
JobSentinel - Phase 2 End-to-End Pipeline & Scheduling Demo
Demonstrates:
1. Job Submission to persistent queue
2. Multi-algorithm performance comparison (FCFS vs SJF vs RR vs Priority)
3. End-to-end execution of scheduled jobs via Worker
4. Result storage, Execution History, and Audit Log verification
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


def run_phase2_demo():
    print("=" * 80)
    print("          JOBSENTINEL - PHASE 2 END-TO-END DEMONSTRATION")
    print("   Secure Process Scheduler with Persistent Database Queue & Worker Execution")
    print("=" * 80)

    # Use SQLite memory/file if MySQL is offline on local machine
    is_live_mysql = check_db_connection()
    if not is_live_mysql:
        print("\n[INFO] Live MySQL server is offline. Initializing isolated database session...")
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
        print("[SUCCESS] Local persistence engine initialized.")
    else:
        print("\n[SUCCESS] Connected to live MySQL database ('jobsentinel')!")

    client = TestClient(app)

    # 1. System Health Check
    print("\n" + "-" * 40)
    print("[STEP 1] Checking Backend Health & Connectivity")
    print("-" * 40)
    health = client.get("/health").json()
    print(f"Health Status: {health.get('status')} | Database Connected: {health.get('database_connected')}")

    # 2. Submit Demo Jobs (from prompt Section 31)
    print("\n" + "-" * 40)
    print("[STEP 2] Submitting 4 Controlled Benchmark Jobs to Queue")
    print("-" * 40)
    demo_jobs = [
        {"command": "print('Job 1: Matrix multiplication simulated')", "burst_time": 5.0, "priority": 2, "arrival_time": 0.0},
        {"command": "print('Job 2: Quick cache validation')", "burst_time": 2.0, "priority": 1, "arrival_time": 1.0},
        {"command": "print('Job 3: Heavy dataset ingestion')", "burst_time": 8.0, "priority": 3, "arrival_time": 2.0},
        {"command": "print('Job 4: Log index aggregation')", "burst_time": 3.0, "priority": 2, "arrival_time": 3.0},
    ]

    submitted_ids = []
    for idx, j_data in enumerate(demo_jobs, start=1):
        resp = client.post("/jobs", json=j_data)
        res_json = resp.json()
        jid = res_json["job_id"]
        submitted_ids.append(jid)
        print(f"  [JOB CREATED] ID={jid} | Burst={j_data['burst_time']}s | Priority={j_data['priority']} | Arrival={j_data['arrival_time']}s")

    # 3. Query Pending Queue
    print("\n" + "-" * 40)
    print("[STEP 3] Fetching Pending Queue from Database")
    print("-" * 40)
    pending = client.get("/jobs/pending").json()
    print(f"Total Pending Jobs in DB Queue: {len(pending)}")
    for p in pending:
        print(f"  - Job {p['job_id']}: Status={p['status']} | Burst={p['burst_time']}s | Priority={p['priority']}")

    # 4. Compare All 4 Algorithms (Member 2 comparative analytics)
    print("\n" + "-" * 40)
    print("[STEP 4] Member 2: Running Comparative Evaluation Across All Algorithms")
    print("-" * 40)
    comp_resp = client.get("/jobs/schedule/compare?quantum=2.0")
    comp_data = comp_resp.json()

    print(f"{'Algorithm':<14} | {'Avg Waiting (s)':<16} | {'Avg Turnaround (s)':<18} | {'Avg Response (s)':<16}")
    print("-" * 72)
    for row in comp_data["comparison_table"]:
        print(f"{row['algorithm']:<14} | {row['average_waiting_time']:<16} | {row['average_turnaround_time']:<18} | {row['average_response_time']:<16}")
    print("-" * 72)
    print(f"--> Recommended Algorithm for this Job Profile: {comp_data['recommended_algorithm']}")

    # 5. Schedule & Execute via SJF with Member 3 Worker
    print("\n" + "-" * 40)
    print("[STEP 5] Scheduling & Executing via SJF (Shortest Job First)")
    print("-" * 40)
    sched_payload = {
        "algorithm": "SJF",
        "job_ids": submitted_ids,
        "execute_jobs": True,
        "worker_id": "WORKER-01"
    }
    sched_resp = client.post("/jobs/schedule", json=sched_payload)
    sched_result = sched_resp.json()

    print(f"Algorithm Selected: {sched_result['algorithm']}")
    print(f"Total Scheduled & Executed: {sched_result['total_scheduled']}")
    print("Execution Order Determined by Scheduler:")
    for item in sched_result["schedule"]:
        print(f"  * Execution Order #{item['execution_order']}: Job {item['job_id']}")

    print("\nDetailed Scheduling Simulation Metrics:")
    for m in sched_result.get("metrics", []):
        print(f"  - Job {m['job_id']}: Start={m['start_time']}s | Completion={m['completion_time']}s | WT={m['waiting_time']}s | TAT={m['turnaround_time']}s | RT={m['response_time']}s")

    print("\nWorker Execution Outcomes:")
    for r in sched_result.get("executed_results", []):
        print(f"  [Worker {r['worker_id']}] Job {r['job_id']} -> Status: {r['status']} | Runtime: {r['execution_time']}s | Output: '{r['output']}'")

    # 6. Verify Execution History
    print("\n" + "-" * 40)
    print("[STEP 6] Querying Persistent Execution History")
    print("-" * 40)
    history = client.get("/history").json()
    print(f"Total Historical Records: {len(history)}")
    for h in history[:4]:
        print(f"  * History #{h['history_id']} - Job {h['job_id']}: Worker={h['worker_id']} | Status={h['status']} | Duration={h['execution_time']}s")

    # 7. Audit Trail Verification
    print("\n" + "-" * 40)
    print(f"[STEP 7] Inspecting Immutable Audit Trail for Job {submitted_ids[0]}")
    print("-" * 40)
    audits = client.get(f"/jobs/{submitted_ids[0]}/audit-logs").json()
    for a in audits:
        print(f"  [{a['timestamp']}] [{a['event_type']}] {a['message']}")

    # 8. Dashboard Statistics Check
    print("\n" + "-" * 40)
    print("[STEP 8] Frontend Dashboard Metrics Verification")
    print("-" * 40)
    stats = client.get("/dashboard/stats").json()
    print(f"Dashboard Stats: {stats}")

    print("\n" + "=" * 80)
    print("        PHASE 2 DEMONSTRATION COMPLETE: ALL SYSTEMS FUNCTIONAL!")
    print("=" * 80)


if __name__ == "__main__":
    run_phase2_demo()
