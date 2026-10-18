from datetime import datetime
from typing import Union
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """Schema for querying audit log records."""
    model_config = ConfigDict(from_attributes=True)

    audit_id: int
    job_id: Union[int, str]
    event_type: str
    message: str
    timestamp: datetime
