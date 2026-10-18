"""
JobSentinel Scheduler - Data Models
Defines internal job representations, execution time slices, metrics, and standard results.
"""

from enum import Enum
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class AlgorithmType(str, Enum):
    FCFS = "FCFS"
    SJF = "SJF"
    ROUND_ROBIN = "ROUND_ROBIN"
    PRIORITY = "PRIORITY"


class ExecutionSlice(BaseModel):
    """Represents a discrete execution time-slice on the CPU (used in Gantt / RR)."""
    job_id: Union[int, str]
    start_time: float
    end_time: float
    duration: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "start_time": round(self.start_time, 2),
            "end_time": round(self.end_time, 2),
            "duration": round(self.duration, 2)
        }


class JobScheduleItem(BaseModel):
    """Internal scheduling representation of a job."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: Union[int, str]
    arrival_time: float
    burst_time: float
    priority: int = 1
    command: Optional[str] = ""
    status: Optional[str] = "PENDING"
    
    # Scheduling metrics (populated during simulation)
    remaining_time: Optional[float] = None
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    waiting_time: Optional[float] = None
    turnaround_time: Optional[float] = None
    response_time: Optional[float] = None
    execution_order: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "command": self.command,
            "arrival_time": round(self.arrival_time, 2),
            "burst_time": round(self.burst_time, 2),
            "priority": self.priority,
            "status": self.status,
            "start_time": round(self.start_time, 2) if self.start_time is not None else None,
            "completion_time": round(self.completion_time, 2) if self.completion_time is not None else None,
            "waiting_time": round(self.waiting_time, 2) if self.waiting_time is not None else None,
            "turnaround_time": round(self.turnaround_time, 2) if self.turnaround_time is not None else None,
            "response_time": round(self.response_time, 2) if self.response_time is not None else None,
            "execution_order": self.execution_order
        }


class AlgorithmMetrics(BaseModel):
    """Aggregate scheduling performance metrics."""
    average_waiting_time: float
    average_turnaround_time: float
    average_response_time: float
    total_burst_time: float = 0.0
    throughput: float = 0.0
    cpu_utilization: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "average_waiting_time": round(self.average_waiting_time, 2),
            "average_turnaround_time": round(self.average_turnaround_time, 2),
            "average_response_time": round(self.average_response_time, 2),
            "total_burst_time": round(self.total_burst_time, 2),
            "throughput": round(self.throughput, 4),
            "cpu_utilization": round(self.cpu_utilization, 2)
        }


class ScheduleResult(BaseModel):
    """Standardized result returned across all algorithms."""
    algorithm: str
    quantum: Optional[float] = None
    total_jobs: int
    jobs: List[JobScheduleItem]
    execution_slices: List[ExecutionSlice] = Field(default_factory=list)
    average_waiting_time: float
    average_turnaround_time: float
    average_response_time: float
    throughput: float = 0.0
    cpu_utilization: float = 100.0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "quantum": self.quantum,
            "total_jobs": self.total_jobs,
            "jobs": [j.to_dict() for j in self.jobs],
            "execution_slices": [s.to_dict() for s in self.execution_slices],
            "average_waiting_time": round(self.average_waiting_time, 2),
            "average_turnaround_time": round(self.average_turnaround_time, 2),
            "average_response_time": round(self.average_response_time, 2),
            "throughput": round(self.throughput, 4),
            "cpu_utilization": round(self.cpu_utilization, 2),
            "message": self.message
        }
