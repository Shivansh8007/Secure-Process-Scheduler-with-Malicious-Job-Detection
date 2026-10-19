import subprocess
import sys
import time
from datetime import datetime


def run_job(worker_id, job_id, task, input_data=""):
    """
    Executes a job task in an isolated process (Member 3 component).
    Attempts execution inside Docker container first. If Docker is unavailable,
    gracefully executes via isolated local Python subprocess.
    """
    print(f"[{worker_id}] started job: {job_id}")

    started_at = datetime.now()
    start = time.time()

    # Try Docker execution first (Member 3's containerized worker)
    use_local_fallback = False
    try:
        result = subprocess.run(
            [
                "docker", "run", "-i", "--rm",
                "--network", "none",
                "--memory", "128m",
                "--cpus", "0.5",
                "python:3.12-slim",
                "python", "-c", task
            ],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Check if Docker failed because daemon is inactive or image missing
        if result.returncode != 0 and ("docker: error" in result.stderr.lower() or "daemon" in result.stderr.lower()):
            use_local_fallback = True
        else:
            completed_at = datetime.now()
            execution_time = time.time() - start

            status_str = "COMPLETED" if result.returncode == 0 else "FAILED"
            print(f"[{worker_id}] completed job {job_id} via Docker (status: {status_str})")

            return {
                "worker_id": worker_id,
                "job_id": job_id,
                "status": status_str,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "exit_code": result.returncode,
                "started_at": started_at,
                "completed_at": completed_at,
                "execution_time": round(execution_time, 2)
            }

    except (FileNotFoundError, PermissionError):
        # Docker binary not installed or not in PATH
        use_local_fallback = True

    except subprocess.TimeoutExpired:
        completed_at = datetime.now()
        print(f"[{worker_id}] job {job_id} timed out after 30s")
        return {
            "worker_id": worker_id,
            "job_id": job_id,
            "status": "FAILED",
            "output": "",
            "error": "Execution timed out",
            "exit_code": None,
            "started_at": started_at,
            "completed_at": completed_at,
            "execution_time": round(time.time() - start, 2)
        }

    # Graceful subprocess fallback when Docker engine is not running
    if use_local_fallback:
        try:
            result = subprocess.run(
                [sys.executable, "-c", task],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=30
            )

            completed_at = datetime.now()
            execution_time = time.time() - start
            status_str = "COMPLETED" if result.returncode == 0 else "FAILED"
            print(f"[{worker_id}] completed job {job_id} via Subprocess (status: {status_str})")

            return {
                "worker_id": worker_id,
                "job_id": job_id,
                "status": status_str,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "exit_code": result.returncode,
                "started_at": started_at,
                "completed_at": completed_at,
                "execution_time": round(execution_time, 2)
            }

        except subprocess.TimeoutExpired:
            completed_at = datetime.now()
            return {
                "worker_id": worker_id,
                "job_id": job_id,
                "status": "FAILED",
                "output": "",
                "error": "Execution timed out",
                "exit_code": None,
                "started_at": started_at,
                "completed_at": completed_at,
                "execution_time": round(time.time() - start, 2)
            }
        except Exception as e:
            completed_at = datetime.now()
            return {
                "worker_id": worker_id,
                "job_id": job_id,
                "status": "FAILED",
                "output": "",
                "error": str(e),
                "exit_code": -1,
                "started_at": started_at,
                "completed_at": completed_at,
                "execution_time": round(time.time() - start, 2)
            }