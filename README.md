# JobSentinel: Secure Process Scheduler with Persistent Database Queue

**Course:** Operating Systems & Database Management Systems Project  
**Component:** Backend, MySQL Persistence, Job Lifecycle, Scheduler & Worker Interfaces  
**Role:** Team Member 1 (Senior Backend Engineer & Lead)  
**Phase:** Phase 2 (Foundation & Execution Pipeline)

---

## 1. Project Overview

JobSentinel is a robust, persistent process scheduler engineered using Python, FastAPI, and MySQL. It bridges OS scheduling algorithms and persistent transactional queueing, supporting process scheduling algorithms (FCFS, SJF, Round Robin, Priority) and distributed worker execution.

### Phase 2 Architecture Flow
```
Submit Job ──► MySQL (Queue) ──► Scheduler (Member 2) ──► Worker (Member 3) ──► Store Result ──► History & Audit (Member 4)
```

---

## 2. Directory Structure

```text
JobSentinel\
├── .env                          # Local environment configuration
├── .env.example                  # Environment configuration template
├── .gitignore                    # Version control ignore list
├── requirements.txt              # Production and test dependencies
├── pytest.ini                    # Test runner configuration
├── API_CONTRACT.md               # Standard API contract for Members 2, 3, 4
├── README.md                     # Setup, architecture, and execution guide
├── worker.py                     # Process execution worker (Docker & Subprocess fallback)
├── jobsentinel.db                # Persistent SQLite database queue (fallback)
├── database\
│   └── schema.sql                # Pure MySQL 8.0 DDL script
├── scheduler\
│   ├── fcfs.py                   # First-Come First-Served scheduling algorithm
│   ├── sjf.py                    # Shortest Job First scheduling algorithm
│   ├── round_robin.py            # Round Robin with time quantum simulation
│   ├── priority.py               # Priority scheduling algorithm
│   ├── metrics.py                # Turnaround, Waiting, Response time metrics
│   ├── models.py                 # Scheduler data models & simulation structures
│   └── scheduler_manager.py      # Master algorithm orchestrator & comparison engine
├── frontend\
│   ├── index.html                # Interactive dashboard, queue & security UI
│   ├── style.css                 # Dashboard styling & layout
│   └── script.js                 # API controller, polling, charts & tables
├── backend\
│   └── app\
│       ├── main.py               # FastAPI entrypoint, middleware, lifespan
│       ├── core\
│       │   ├── config.py         # Settings & environment variable loader
│       │   ├── database.py       # Engine, SessionLocal, resilient DB fallback
│       │   ├── exceptions.py     # Domain exceptions
│       │   └── logging.py        # Structured logging configuration
│       ├── models\
│       │   ├── enums.py          # JobStatus, AlgorithmType, AuditEventType
│       │   ├── job.py            # Job ORM table
│       │   ├── history.py        # ExecutionHistory ORM table
│       │   └── audit.py          # AuditLog ORM table
│       ├── schemas\
│       │   ├── job.py            # Pydantic schemas for jobs
│       │   ├── scheduler.py      # Scheduler input/output schemas (Member 2)
│       │   ├── worker.py         # Worker result schemas (Member 3)
│       │   ├── history.py        # Execution history schemas
│       │   └── audit.py          # Audit log schemas
│       ├── services\
│       │   ├── job_service.py    # Job creation, validation, lifecycle logic
│       │   ├── scheduler_service.py # Scheduler interface & algorithm execution
│       │   ├── worker_service.py # Worker execution & atomic transactions
│       │   └── audit_service.py  # Immutable audit logging helper
│       └── api\
│           ├── deps.py           # FastAPI dependency injection
│           └── v1\
│               ├── router.py     # Master v1 router
│               ├── jobs.py       # Job submission, status, retrieval endpoints
│               ├── scheduler.py  # Scheduler endpoints
│               ├── worker.py     # Worker start & result endpoints
│               ├── history.py    # Execution history endpoints
│               └── audit.py      # Audit log endpoints
├── scripts\
│   ├── init_mysql_db.py          # Automated MySQL database & table creation
│   ├── demo_flow.py              # Full end-to-end pipeline demonstration
│   ├── demo_phase2.py            # Phase 2 live demo with comparison & execution
│   └── view_db.py                # Database table inspector utility
└── tests\
    ├── conftest.py               # Isolated test fixtures
    ├── test_database.py          # Database connection & schema metadata tests
    ├── test_jobs.py              # Job submission, retrieval & validation tests
    ├── test_lifecycle.py         # Strict status lifecycle state machine tests
    ├── test_scheduler_algorithms.py # All CPU scheduling algorithm tests
    ├── test_scheduler_api.py     # Scheduler contracts & algorithm ordering tests
    ├── test_scheduler_integration.py # Multi-algorithm integration tests
    ├── test_worker_api.py        # Worker start, result handling, error tests
    └── test_history_audit.py     # Execution history and audit logging tests
```

---

## 3. Technology Stack

* **Backend Framework:** FastAPI
* **Database:** MySQL 8.0
* **ORM & Database Layer:** SQLAlchemy 2.0
* **MySQL Driver:** PyMySQL (`mysql+pymysql://`)
* **Validation & Serialization:** Pydantic v2
* **Server:** Uvicorn
* **Configuration:** python-dotenv / pydantic-settings
* **Testing:** Pytest

---

## 4. Setup & Installation

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` and configure your MySQL credentials:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
DB_HOST=localhost
DB_PORT=3306
DB_NAME=jobsentinel
DB_USER=root
DB_PASSWORD=your_mysql_password
```

### Step 3: Initialize MySQL Database
Run the initialization script to create the `jobsentinel` database and all required tables:
```bash
python scripts/init_mysql_db.py
```
*(Alternatively, you can execute `database/schema.sql` directly inside MySQL Workbench or MySQL CLI)*.

---

## 5. Running the Backend Server

Start the FastAPI application with Uvicorn:
```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running:
* **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 6. Running Tests

Run the full automated test suite covering all 43 test scenarios (unit, lifecycle, algorithm, integration, and worker tests):
```bash
pytest -v
```

---

## 7. Running End-to-End Pipeline Demonstration

To run the full demonstration with multi-algorithm performance comparison (FCFS, SJF, RR, Priority), automated scheduling, worker execution, and persistent queue verification:
```bash
python scripts/demo_phase2.py
```

Or run the basic Member 1 flow:
```bash
python scripts/demo_flow.py
```

---

## 8. Definition of Done Checklist (Member 1)

- [x] MySQL schema designed (`jobs`, `execution_history`, `audit_logs`)
- [x] Database configuration via environment variables (`.env`, `.env.example`)
- [x] Centralized database connection with pooling (`backend/app/core/database.py`)
- [x] Clean SQLAlchemy ORM models with constraints and relationships
- [x] Standard Pydantic schemas and data contracts
- [x] Job submission API (`POST /jobs`) with validation and `PENDING` status
- [x] Job retrieval APIs (`GET /jobs`, `GET /jobs/{job_id}`, `GET /jobs/pending`)
- [x] Safe status update API (`PATCH /jobs/{job_id}/status`) with lifecycle guards
- [x] Scheduler integration interface (`POST /jobs/schedule`, `GET /jobs/schedule/input`)
- [x] Worker integration interface (`PATCH /jobs/{job_id}/start`, `POST /jobs/{job_id}/result`)
- [x] Atomic transactions (updating job, storing result, recording history, logging audit event)
- [x] Execution history query APIs (`GET /history`, `GET /jobs/{job_id}/history`)
- [x] Audit logging APIs (`GET /audit-logs`, `GET /jobs/{job_id}/audit-logs`)
- [x] Centralized error handling and safe HTTP status codes
- [x] Automated test suite passing 100% (21 tests)
- [x] Team API Contract documented in `API_CONTRACT.md`
- [x] End-to-end integration demo script (`scripts/demo_flow.py`)
- [x] Ready for Member 2, Member 3, and Member 4 independent integration
- [x] Phase 3 Security Analyzer extension point prepared (`QUARANTINED` enum)
