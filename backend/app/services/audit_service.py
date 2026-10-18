from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.models.audit import AuditLog
from backend.app.models.enums import AuditEventType
from backend.app.core.logging import logger


def record_audit_log(
    db: Session,
    job_id: str,
    event_type: AuditEventType | str,
    message: str
) -> AuditLog:
    """Create and append an immutable audit log entry within the active transaction."""
    event_val = event_type.value if isinstance(event_type, AuditEventType) else str(event_type)
    
    audit_entry = AuditLog(
        job_id=str(job_id),
        event_type=event_val,
        message=message,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(audit_entry)
    logger.info("[AUDIT] [%s] Job '%s': %s", event_val, job_id, message)
    return audit_entry
