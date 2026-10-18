from datetime import datetime
from typing import Optional, Union
from pydantic import BaseModel, ConfigDict


class ExecutionHistoryResponse(BaseModel):
    """Schema for querying job execution history."""
    model_config = ConfigDict(from_attributes=True)

    history_id: int
    job_id: Union[int, str]
    worker_id: str
    status: str
    output: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    created_at: datetime
