"""
Multi-File SHA-256 Integrity Manifest & TOCTOU Protection Service for JobSentinel

Generates, stores, and validates comprehensive file integrity manifests for
multi-file projects, and creates isolated, write-protected execution snapshots
to eliminate Time-of-Check to Time-of-Use (TOCTOU) tampering.
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from backend.app.core.logging import logger
from backend.app.services.file_identifier import FileIdentifier, compute_file_sha256


class IntegrityViolationException(Exception):
    """Raised when workspace files fail integrity verification."""
    pass


def utc_now_iso() -> str:
    """Return timezone-naive UTC timestamp string."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def normalize_manifest_path(path: Union[str, Path]) -> str:
    """
    Normalizes file path consistently across Windows and Linux:
    - Forward slashes only
    - No leading slashes
    - No path traversal ('..')
    - Rejects absolute paths or drive letters
    """
    raw = str(path).replace("\\", "/").strip()

    # Reject null bytes
    if "\x00" in raw:
        raise ValueError(f"Null byte detected in path: '{raw}'")

    # Reject absolute or drive paths
    if raw.startswith("/") or ":" in raw:
        raise ValueError(f"Absolute or drive path rejected: '{raw}'")

    parts = [p for p in raw.split("/") if p and p != "."]
    if ".." in parts:
        raise ValueError(f"Path traversal detected in path: '{raw}'")

    normalized = "/".join(parts)
    if not normalized:
        raise ValueError("Normalized path cannot be empty.")

    return normalized


def generate_integrity_manifest(
    project_dir: Path,
    job_id: str
) -> Dict[str, Any]:
    """
    Enumerates all regular files inside `project_dir` and builds a complete
    SHA-256 integrity manifest with file identification metadata.
    """
    root = Path(project_dir).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Project directory does not exist or is not a directory: {project_dir}")

    manifest_files: Dict[str, Dict[str, Any]] = {}
    normalized_path_lookup: Dict[str, str] = {}  # case-folded lookup for collision detection
    total_bytes = 0

    for item in sorted(root.glob("**/*")):
        if not item.is_file():
            continue

        rel_path = item.relative_to(root)
        norm_path = normalize_manifest_path(rel_path)

        # Detect duplicate or conflicting normalized paths (e.g. casing conflicts on Windows)
        folded = norm_path.lower()
        if folded in normalized_path_lookup:
            conflict_orig = normalized_path_lookup[folded]
            if conflict_orig != norm_path:
                raise ValueError(
                    f"Conflicting normalized paths detected in archive: '{conflict_orig}' vs '{norm_path}'"
                )
            else:
                raise ValueError(f"Duplicate file entry detected: '{norm_path}'")
        normalized_path_lookup[folded] = norm_path

        # Identify file and compute SHA-256
        ident = FileIdentifier.identify_file(item, normalized_path=norm_path)

        total_bytes += ident.file_size
        manifest_files[norm_path] = {
            "path": norm_path,
            "sha256": ident.sha256,
            "size_bytes": ident.file_size,
            "file_type": ident.detected_type,
            "mime_type": ident.mime_type,
            "extension": ident.extension,
            "is_supported": ident.is_supported_for_scanning,
            "extension_mismatch": ident.extension_mismatch,
            "error_details": ident.error_details,
        }

    return {
        "job_id": str(job_id),
        "manifest_version": "1.0",
        "created_at": utc_now_iso(),
        "file_count": len(manifest_files),
        "total_bytes": total_bytes,
        "files": manifest_files,
    }


def verify_integrity_manifest(
    target_dir: Path,
    manifest: Dict[str, Any]
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Verifies that `target_dir` matches the expected manifest completely:
    - Every manifest file exists and has matching SHA-256 hash.
    - No unexpected files exist in `target_dir` that are not in the manifest.
    - All files can be read without errors.
    - Detects modified, missing, and additional files.
    Returns: (is_valid, error_reason, details_dict)
    """
    root = Path(target_dir).resolve()
    if not root.exists() or not root.is_dir():
        return False, f"Target directory does not exist: {target_dir}", {}

    manifest_files: Dict[str, Dict[str, Any]] = manifest.get("files", {})
    verified_files: List[str] = []
    modified_files: List[Dict[str, str]] = []
    missing_files: List[str] = []
    unexpected_files: List[str] = []
    unreadable_files: List[str] = []

    # 1. Check every file recorded in the manifest
    for norm_path, info in manifest_files.items():
        file_path = root / norm_path
        if not file_path.exists() or not file_path.is_file():
            missing_files.append(norm_path)
            continue

        try:
            current_hash = compute_file_sha256(file_path)
            expected_hash = info.get("sha256")
            if current_hash != expected_hash:
                modified_files.append({
                    "path": norm_path,
                    "expected_sha256": expected_hash,
                    "actual_sha256": current_hash,
                })
            else:
                verified_files.append(norm_path)
        except Exception as e:
            unreadable_files.append(f"{norm_path} ({str(e)})")

    # 2. Check for unexpected additional files on disk
    for item in root.glob("**/*"):
        if not item.is_file():
            continue
        try:
            rel = item.relative_to(root)
            norm = normalize_manifest_path(rel)
            if norm not in manifest_files:
                unexpected_files.append(norm)
        except Exception:
            unexpected_files.append(str(item))

    # Formulate results
    details = {
        "verified_count": len(verified_files),
        "missing_files": missing_files,
        "modified_files": modified_files,
        "unexpected_files": unexpected_files,
        "unreadable_files": unreadable_files,
    }

    if missing_files:
        msg = f"Integrity violation: Missing {len(missing_files)} file(s): {', '.join(missing_files[:5])}"
        return False, msg, details

    if modified_files:
        mod_details = [f"{m['path']} (expected {m['expected_sha256'][:8]}..., got {m['actual_sha256'][:8]}...)" for m in modified_files[:3]]
        msg = f"Integrity violation: Modified file(s) detected: {'; '.join(mod_details)}"
        return False, msg, details

    if unexpected_files:
        msg = f"Integrity violation: Unexpected additional file(s) detected: {', '.join(unexpected_files[:5])}"
        return False, msg, details

    if unreadable_files:
        msg = f"Integrity violation: Unreadable file(s) detected: {', '.join(unreadable_files[:5])}"
        return False, msg, details

    return True, None, details


def create_verified_execution_snapshot(
    source_dir: Path,
    manifest: Dict[str, Any],
    snapshot_dir: Path
) -> Path:
    """
    TOCTOU Protection:
    1. Creates a dedicated execution snapshot directory.
    2. Copies all verified manifest files from source_dir into snapshot_dir.
    3. Runs verify_integrity_manifest() on snapshot_dir.
    4. Makes files read-only on disk to prevent tampering between check and execution.
    5. Returns the verified snapshot directory to be mounted into Docker as :ro.
    """
    src_root = Path(source_dir).resolve()
    snap_root = Path(snapshot_dir).resolve()

    # Clean existing snapshot directory
    if snap_root.exists():
        def _force_rm(func, path, _):
            try:
                os.chmod(path, 0o777)
                func(path)
            except Exception:
                pass
        shutil.rmtree(snap_root, onerror=_force_rm)

    snap_root.mkdir(parents=True, exist_ok=True)

    manifest_files: Dict[str, Dict[str, Any]] = manifest.get("files", {})

    # Copy files according to manifest
    for norm_path in manifest_files:
        src_file = src_root / norm_path
        dest_file = snap_root / norm_path

        if not src_file.exists() or not src_file.is_file():
            shutil.rmtree(snap_root, ignore_errors=True)
            raise IntegrityViolationException(
                f"Cannot create execution snapshot: Source file '{norm_path}' is missing."
            )

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)

    # Verify the snapshot directory before execution
    is_valid, err, details = verify_integrity_manifest(snap_root, manifest)
    if not is_valid:
        shutil.rmtree(snap_root, ignore_errors=True)
        raise IntegrityViolationException(f"Snapshot integrity verification failed: {err}")

    # Set read-only permissions on snapshot files to prevent untrusted modification
    for item in snap_root.glob("**/*"):
        if item.is_file():
            try:
                os.chmod(item, 0o444)  # Read-only
            except Exception:
                pass

    logger.info("Created verified execution snapshot for Job '%s' at: %s", manifest.get("job_id"), snap_root)
    return snap_root

