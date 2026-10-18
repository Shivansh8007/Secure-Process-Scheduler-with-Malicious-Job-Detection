class JobSentinelException(Exception):
    """Base exception for all JobSentinel domain errors."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class JobNotFoundException(JobSentinelException):
    def __init__(self, job_id: str):
        super().__init__(f"Job with ID '{job_id}' not found.", status_code=404)


class JobAlreadyExistsException(JobSentinelException):
    def __init__(self, job_id: str):
        super().__init__(f"Job with ID '{job_id}' already exists.", status_code=409)


class InvalidStatusTransitionException(JobSentinelException):
    def __init__(self, current_status: str, target_status: str, job_id: str):
        super().__init__(
            f"Invalid lifecycle transition for Job '{job_id}': cannot transition from {current_status} to {target_status}.",
            status_code=422
        )


class InvalidSchedulingAlgorithmException(JobSentinelException):
    def __init__(self, algorithm: str):
        super().__init__(
            f"Unsupported scheduling algorithm '{algorithm}'. Must be one of FCFS, SJF, ROUND_ROBIN, PRIORITY.",
            status_code=422
        )


class DatabaseOperationException(JobSentinelException):
    def __init__(self, message: str):
        super().__init__(f"Database operation failed: {message}", status_code=500)
