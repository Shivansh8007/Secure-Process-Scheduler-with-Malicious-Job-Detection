from enum import Enum


class JobStatus(str, Enum):
    """Lifecycle statuses for JobSentinel jobs."""
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    # Future Phase 3 Extension Point (Security / Malicious Job Quarantine)
    # Kept available in enum and DB schema so no schema redesign is needed later
    QUARANTINED = "QUARANTINED"


class AlgorithmType(str, Enum):
    """Scheduling algorithms supported by JobSentinel."""
    FCFS = "FCFS"
    SJF = "SJF"
    ROUND_ROBIN = "ROUND_ROBIN"
    PRIORITY = "PRIORITY"


class AuditEventType(str, Enum):
    """Audit log event types for traceability."""
    JOB_CREATED = "JOB_CREATED"
    JOB_SCHEDULED = "JOB_SCHEDULED"
    JOB_STARTED = "JOB_STARTED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
