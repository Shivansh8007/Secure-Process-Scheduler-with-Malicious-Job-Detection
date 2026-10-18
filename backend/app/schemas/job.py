from datetime import datetime
from typing import Optional, Union
from pydantic import BaseModel, Field, ConfigDict
from backend.app.models.enums import JobStatus


class JobCreate(BaseModel):
    """Schema for job submission."""
    command: str = Field(..., min_length=1, description="Command or script to execute", examples=["python test.py"])
    burst_time: float = Field(..., gt=0, description="Estimated CPU burst time required", examples=[5.0])
    priority: int = Field(default=1, ge=0, description="Process priority (e.g. 1 = standard)", examples=[2])
    arrival_time: Optional[float] = Field(default=None, description="Arrival time (defaults to server timestamp)")
    job_id: Optional[Union[int, str]] = Field(default=None, description="Optional custom unique job ID")


class JobStatusUpdate(BaseModel):
    """Schema for updating job status."""
    status: JobStatus = Field(..., description="Target status transition")


class JobStartRequest(BaseModel):
    """Schema for starting a job."""
    worker_id: str = Field(default="worker-1", description="Identifier of the executing worker")


class JobResponse(BaseModel):
    """Standardized Job representation across the platform."""
    model_config = ConfigDict(from_attributes=True)

    job_id: Union[int, str]
    command: str
    arrival_time: float
    burst_time: float
    priority: int
    status: JobStatus
    algorithm: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobSubmissionResponse(BaseModel):
    """Response returned upon successful job submission."""
    job_id: Union[int, str]
    status: JobStatus
    message: str
    job: Optional[JobResponse] = None
