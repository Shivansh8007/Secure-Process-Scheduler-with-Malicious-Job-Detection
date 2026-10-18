from typing import Optional, Union
from pydantic import BaseModel, Field
from backend.app.models.enums import JobStatus
from backend.app.schemas.job import JobResponse


class WorkerStartRequest(BaseModel):
    """Payload when a worker starts executing a job."""
    worker_id: str = Field(default="worker-1", description="Identifier of executing worker", examples=["worker-1"])


class WorkerResultRequest(BaseModel):
    """Payload when a worker finishes executing a job (Member 3 contract)."""
    worker_id: str = Field(..., description="Worker identifier", examples=["worker-1"])
    status: JobStatus = Field(
        ...,
        description="Execution outcome: COMPLETED or FAILED",
        examples=["COMPLETED"]
    )
    output: Optional[str] = Field(default=None, description="Standard output captured from execution")
    error_message: Optional[str] = Field(default=None, description="Standard error or exception traceback")
    execution_time: Optional[float] = Field(
        default=None,
        ge=0,
        description="Measured execution runtime in seconds",
        examples=[2.31]
    )


class WorkerResultResponse(BaseModel):
    """Response returned upon saving execution results."""
    job_id: Union[int, str]
    status: JobStatus
    worker_id: str
    execution_time: Optional[float] = None
    message: str
    job: Optional[JobResponse] = None
