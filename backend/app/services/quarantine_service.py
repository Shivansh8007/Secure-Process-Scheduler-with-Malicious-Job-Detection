"""
Quarantine Service for JobSentinel
Manages isolated quarantine storage under `storage/quarantine/job_{job_id}/`,
enforcing restricted permissions, unique safe filenames, collision avoidance,
and zero-execution policies for suspicious or infected payloads.
"""
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from sqlalchemy.orm import Session

from backend.app.core.storage import get_job_quarantine_dir, clean_job_storage
from backend.app.core.logging import logger
from backend.app.models.job import Job
from backend.app.models.security_scan import SecurityScan
from backend.app.models.enums import JobStatus, AuditEventType
from backend.app.services.audit_service import record_audit_log


def utc_now() -> datetime:
    """Return timezone-naive UTC datetime compatible with MySQL DATETIME."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sanitize_filename_for_quarantine(filename: str) -> str:
    """
    Sanitizes raw filenames to prevent path traversal, drive letters, and dangerous characters.
    Replaces unsafe characters with underscores.
    """
    clean = filename.replace("\\", "/").split("/")[-1].strip()
    # Remove null bytes and non-printable characters
    clean = re.sub(r"[\x00-\x1f\x7f]", "", clean)
    # Strip dangerous shell/filesystem characters
    clean = re.sub(r'[<>:"/\\|?*]', "_", clean)
    if not clean or clean.startswith("."):
        clean = f"quarantined_payload_{clean.lstrip('.')}"
    return clean


def generate_unique_quarantine_filename(original_filename: str) -> str:
    """
    Generates a unique safe filename to prevent overwriting when multiple
    files with identical names are quarantined.
    Format: YYYYMMDD_HHMMSS_<short_uuid>_<sanitized_name>
    """
    clean_base = sanitize_filename_for_quarantine(original_filename)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:8]
    return f"{ts}_{rand_suffix}_{clean_base}"


def quarantine_file(
    db: Session,
    job_id: str,
    file_source: Union[str, Path, bytes],
    original_filename: str,
    threat_name: str,
    sha256_hash: str,
    scanner_version: Optional[str] = None,
    error_details: Optional[str] = None,
    update_job_status: bool = True,
) -> Path:
    """
    Moves an infected or suspicious file into dedicated quarantine storage:
    1. Locates storage/quarantine/job_{job_id}/
    2. Generates a collision-resistant unique safe filename
    3. Moves/writes the suspicious file into quarantine
    4. Enforces restricted filesystem permissions (0o600 / non-executable)
    5. Preserves original filename in database
    6. Updates Job status to QUARANTINED
    7. Inserts SecurityScan record with detection name, SHA-256, and timestamp
    8. Records immutable AuditLog entry
    """
    quarantine_dir = get_job_quarantine_dir(job_id)
    safe_name = generate_unique_quarantine_filename(original_filename)
    quarantine_dest = (quarantine_dir / safe_name).resolve()

    # Prevent path traversal outside the quarantine folder
    quarantine_dest.relative_to(quarantine_dir.resolve())

    # Write or move payload
    if isinstance(file_source, bytes):
        with open(quarantine_dest, "wb") as f:
            f.write(file_source)
    else:
        source_p = Path(file_source).resolve()
        if source_p.exists() and source_p.is_file():
            shutil.move(str(source_p), str(quarantine_dest))
        else:
            raise FileNotFoundError(f"Source file to quarantine not found: {source_p}")

    # Restrict permissions: read/write only by owner, never executable
    try:
        os.chmod(quarantine_dest, 0o600)
    except Exception as e:
        logger.debug("Failed to set restricted permissions on '%s': %s", quarantine_dest, str(e))

    # Clean up normal upload workspace if present
    clean_job_storage(job_id)

    # Update or fetch Job record in database
    job = db.query(Job).filter(Job.job_id == str(job_id)).first()
    if job and update_job_status:
        job.status = JobStatus.QUARANTINED.value
        if not job.expected_sha256:
            job.expected_sha256 = sha256_hash
        if not job.zip_original_filename and original_filename:
            job.zip_original_filename = original_filename

    # Record security scan record
    scan_entry = SecurityScan(
        job_id=str(job_id),
        original_filename=original_filename,
        sha256_hash=sha256_hash,
        scan_result="INFECTED",
        threat_name=threat_name,
        scanner_version=scanner_version,
        scan_timestamp=utc_now(),
        quarantine_location=str(quarantine_dest),
        error_details=error_details,
    )
    db.add(scan_entry)

    # Record audit log entry
    record_audit_log(
        db,
        job_id=str(job_id),
        event_type=AuditEventType.JOB_QUARANTINED,
        message=(
            f"Malware detected: '{threat_name}' in '{original_filename}'. "
            f"Original file safely quarantined to: {quarantine_dest.name} (SHA-256: {sha256_hash})"
        ),
    )

    db.commit()
    logger.warning(
        "Job '%s' quarantined. File '%s' moved to '%s' (Threat: %s)",
        job_id, original_filename, quarantine_dest, threat_name
    )
    return quarantine_dest

