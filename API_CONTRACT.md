# JobSentinel API Contract & Integration Specifications

**Subsystem:** Backend, MySQL Persistence, Job Queue, Lifecycle Engine  
**Author:** Team Member 1 (Database & Backend Lead)  
**Target Audience:** Member 2 (Scheduler), Member 3 (Worker/Execution), Member 4 (Frontend/UI)  
**Version:** Phase 2.0.0 (Foundation & Execution Pipeline)  

---

## 1. Architectural Overview & Boundaries

The backend serves as the centralized source of truth and state machine for JobSentinel.
Database internals (MySQL, connection pooling, SQL queries) are completely abstracted behind clean REST API boundaries.

```
       [Member 4: Frontend]
                │
                ▼ (HTTP REST)
┌───────────────────────────────────────────────┐
│           FastAPI Backend (Member 1)          │
│   • MySQL Persistence & Queue                 │
│   • Atomic Transactions                       │
│   • Lifecycle State Machine                   │
│   • Audit Trail & History Storage             │
└──────────────┬────────────────┬───────────────┘
               │                │
               ▼                ▼
     [Member 2: Scheduler]   [Member 3: Worker]
       • FCFS                  • Process Execution
       • SJF                   • Output/Error Capture
       • Priority              • Timing Measurement
       • Round Robin
```

---

## 2. Standard Job Object

Across all responses, a Job is represented with the following schema:

```json
{
  "job_id": 101,
  "command": "python test.py",
  "arrival_time": 1711800000.123,
  "burst_time": 5.0,
  "priority": 2,
  "status": "PENDING",
  "algorithm": null,
  "created_at": "2026-10-03T18:00:00",
  "started_at": null,
  "completed_at": null
}
```

### Key Field Descriptions for Team Members
| Field | Type | Description | Primary Consumer |
|---|---|---|---|
| `job_id` | `string` / `integer` | Unique process identifier (e.g. `101`, `102`) | All Members |
| `command` | `string` | The shell/script command to run | Member 3 (Worker) |
| `arrival_time` | `float` | Unix timestamp or simulation arrival time | Member 2 (Scheduler) |
| `burst_time` | `float` | Estimated CPU execution duration | Member 2 (Scheduler) |
| `priority` | `integer` | Process priority (lower value = higher priority) | Member 2 (Scheduler) |
| `status` | `string` | Current lifecycle state | All Members |
| `algorithm` | `string \| null` | Algorithm that scheduled the job (`FCFS`, `SJF`, etc.) | Member 4 (Frontend) |
| `started_at` | `string \| null` | ISO timestamp when worker started execution | Member 4 (Frontend) |
| `completed_at` | `string \| null` | ISO timestamp when execution completed | Member 4 (Frontend) |

---

## 3. Job Lifecycle State Machine

The backend enforces strict state transitions. Invalid transitions will return **HTTP 422 Unprocessable Content**.

```
    [PENDING]
        │
        ▼ (Scheduled by Member 2)
   [SCHEDULED]
        │
        ▼ (Worker starts execution)
    [RUNNING]
        │
        ├──► [COMPLETED] (Process succeeded)
        │
        └──► [FAILED]    (Process errored / timeout)
```

> **Future Extension Point (Phase 3):**  
> `QUARANTINED` is reserved for malicious job isolation in Phase 3. It does not affect Phase 2 scheduler or worker operations.

---

## 4. Member 2: Scheduler Integration Interface

Member 2 is responsible for scheduling algorithms: **FCFS**, **SJF**, **ROUND_ROBIN**, and **PRIORITY**.
The backend provides two endpoints for Member 2.

### 4.1 Fetching Jobs for Scheduling
* **Endpoint:** `GET /jobs/pending` (or `GET /jobs/schedule/input`)
* **Response (Scheduler Input):**
```json
[
  {
    "job_id": 101,
    "arrival_time": 10.0,
    "burst_time": 5.0,
    "priority": 2,
    "status": "PENDING"
  },
  {
    "job_id": 102,
    "arrival_time": 5.0,
    "burst_time": 2.0,
    "priority": 1,
    "status": "PENDING"
  }
]
```

### 4.2 Submitting Scheduling Decisions
* **Endpoint:** `POST /jobs/schedule`
* **Request:**
```json
{
  "algorithm": "SJF",
  "time_quantum": 2.0,
  "job_ids": ["101", "102"]
}
```
* **Response (Scheduler Output):**
```json
{
  "algorithm": "SJF",
  "total_scheduled": 2,
  "schedule": [
    {
      "job_id": "102",
      "execution_order": 1
    },
    {
      "job_id": "101",
      "execution_order": 2
    }
  ],
  "scheduled_jobs": [ ... ],
  "message": "Successfully scheduled 2 jobs using SJF."
}
```
* **Backend Action:** The backend transitions each scheduled job to `SCHEDULED`, writes an immutable `JOB_SCHEDULED` audit event, and records the `algorithm` in MySQL.

---

## 5. Member 3: Worker Integration Interface

Member 3 is responsible for process execution, output capture, error capture, and execution time measurement.

### 5.1 Signal Job Execution Start
When a worker dequeues a scheduled job and begins execution:
* **Endpoint:** `PATCH /jobs/{job_id}/start`
* **Request:**
```json
{
  "worker_id": "worker-1"
}
```
* **Response:**
```json
{
  "job_id": "101",
  "command": "python test.py",
  "status": "RUNNING",
  "started_at": "2026-10-03T18:15:30.123456"
}
```
* **Backend Action:** Verifies current status is `SCHEDULED`, transitions status to `RUNNING`, sets `started_at`, and writes `JOB_STARTED` audit entry.

### 5.2 Submit Execution Results
When worker completes execution:
* **Endpoint:** `POST /jobs/{job_id}/result`
* **Request:**
```json
{
  "worker_id": "worker-1",
  "status": "COMPLETED",
  "output": "Process finished successfully with exit code 0\n[Output data...]",
  "error_message": null,
  "execution_time": 2.31
}
```
*(For failures, pass `"status": "FAILED"` and `"error_message": "Traceback / stderr..."`)*.

* **Response:**
```json
{
  "job_id": "101",
  "status": "COMPLETED",
  "worker_id": "worker-1",
  "execution_time": 2.31,
  "message": "Execution result stored successfully with status COMPLETED."
}
```
* **Backend Action (Single Atomic Transaction):**
  1. Updates `job.status` to `COMPLETED` or `FAILED`.
  2. Sets `job.completed_at`.
  3. Inserts an immutable row into `execution_history`.
  4. Inserts an audit event (`JOB_COMPLETED` or `JOB_FAILED`).
  5. Commits all records in a single database transaction.

---

## 6. Member 4: Frontend / Dashboard Endpoints

Member 4 can consume all endpoints to build the real-time scheduling dashboard.

### 6.1 Job Submission
* **Endpoint:** `POST /jobs`
* **Request:**
```json
{
  "command": "python test.py",
  "burst_time": 5.0,
  "priority": 2,
  "arrival_time": 10.0
}
```
* **Response:**
```json
{
  "job_id": "101",
  "status": "PENDING",
  "message": "Job submitted successfully"
}
```

### 6.2 Job Listing & Filtering
* **List all jobs:** `GET /jobs?limit=50&offset=0`
* **Filter by status:** `GET /jobs?status=PENDING`
* **Get single job:** `GET /jobs/{job_id}`
* **Get pending queue:** `GET /jobs/pending`

### 6.3 Execution History
* **Global history:** `GET /history?limit=100&offset=0`
* **Per-job history:** `GET /jobs/{job_id}/history`
* **Response schema:**
```json
[
  {
    "history_id": 1,
    "job_id": "101",
    "worker_id": "worker-1",
    "status": "COMPLETED",
    "output": "Hello World",
    "error_message": null,
    "started_at": "2026-10-03T18:15:30",
    "completed_at": "2026-10-03T18:15:32",
    "execution_time": 2.31,
    "created_at": "2026-10-03T18:15:32"
  }
]
```

### 6.4 Audit Logs
* **System audit logs:** `GET /audit-logs?limit=100`
* **Job audit logs:** `GET /jobs/{job_id}/audit-logs`

---

## 7. HTTP Status Codes & Error Handling

Standard HTTP response codes are guaranteed:
* `200 OK`: Request succeeded.
* `201 Created`: Job created and stored.
* `400 Bad Request`: Malformed request parameters.
* `404 Not Found`: Job or resource does not exist.
* `409 Conflict`: Attempted to create duplicate `job_id`.
* `422 Unprocessable Content`: Invalid lifecycle transition or validation error.
* `500 Internal Server Error`: Generic database or internal failure (no internal credentials leaked).

**Error Response Format:**
```json
{
  "error": "InvalidStatusTransitionException",
  "detail": "Invalid lifecycle transition for Job '101': cannot transition from PENDING to RUNNING."
}
```
