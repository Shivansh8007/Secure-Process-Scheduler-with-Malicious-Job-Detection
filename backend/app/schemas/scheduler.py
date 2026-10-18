from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field
from backend.app.models.enums import AlgorithmType, JobStatus
from backend.app.schemas.job import JobResponse


class SchedulerInputJob(BaseModel):
    """Input payload format for scheduling algorithms (Member 2 contract)."""
    job_id: Union[int, str]
    arrival_time: float
    burst_time: float
    priority: int
    status: JobStatus


class JobOrderAssignment(BaseModel):
    """Output item returned by scheduler indicating execution order."""
    job_id: Union[int, str]
    execution_order: int


class JobExecutionMetricItem(BaseModel):
    """Detailed scheduling metrics for an individual job."""
    job_id: Union[int, str]
    execution_order: int
    arrival_time: float
    burst_time: float
    priority: int
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    waiting_time: Optional[float] = None
    turnaround_time: Optional[float] = None
    response_time: Optional[float] = None


class ExecutionSliceResponse(BaseModel):
    """Discrete time slice representation."""
    job_id: Union[int, str]
    start_time: float
    end_time: float
    duration: float


class SchedulerScheduleRequest(BaseModel):
    """Request payload to trigger scheduling algorithm."""
    algorithm: AlgorithmType = Field(..., description="Target scheduling algorithm", examples=["FCFS"])
    time_quantum: Optional[float] = Field(default=2.0, gt=0, description="Time quantum for Round Robin")
    job_ids: Optional[List[Union[int, str]]] = Field(
        default=None,
        description="Optional list of specific job IDs to schedule. Defaults to all PENDING jobs."
    )
    execute_jobs: Optional[bool] = Field(
        default=False,
        description="If True, dispatches scheduled jobs to workers for immediate execution"
    )
    worker_id: Optional[str] = Field(
        default="worker-1",
        description="Worker ID for execution dispatch"
    )


class SchedulerScheduleResponse(BaseModel):
    """Response returned after scheduling jobs with complete metrics."""
    algorithm: AlgorithmType
    time_quantum: Optional[float] = None
    total_scheduled: int
    schedule: List[JobOrderAssignment]
    metrics: Optional[List[JobExecutionMetricItem]] = None
    execution_slices: Optional[List[ExecutionSliceResponse]] = None
    average_waiting_time: Optional[float] = None
    average_turnaround_time: Optional[float] = None
    average_response_time: Optional[float] = None
    throughput: Optional[float] = None
    cpu_utilization: Optional[float] = None
    scheduled_jobs: List[JobResponse]
    executed_results: Optional[List[Dict[str, Any]]] = None
    message: str


class AlgorithmComparisonSummaryItem(BaseModel):
    algorithm: str
    average_waiting_time: float
    average_turnaround_time: float
    average_response_time: float
    throughput: float
    cpu_utilization: float


class ProcessAlgorithmMetric(BaseModel):
    order: Optional[int] = None
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    waiting_time: Optional[float] = None
    turnaround_time: Optional[float] = None
    response_time: Optional[float] = None


class ProcessComparisonItem(BaseModel):
    job_id: Union[int, str]
    command: Optional[str] = ""
    arrival_time: float
    burst_time: float
    priority: int
    algorithms: Dict[str, ProcessAlgorithmMetric]


class CustomProcessItem(BaseModel):
    job_id: Union[int, str]
    arrival_time: float = 0.0
    burst_time: float = 1.0
    priority: int = 1
    command: Optional[str] = ""


class CustomComparisonRequest(BaseModel):
    quantum: float = Field(default=2.0, gt=0, description="Time quantum for Round Robin")
    processes: List[CustomProcessItem]


class SchedulerComparisonResponse(BaseModel):
    """Response returned for algorithm comparative evaluation."""
    total_jobs: int
    quantum_used_for_rr: float
    comparison_table: List[AlgorithmComparisonSummaryItem]
    recommended_algorithm: str
    process_comparison: Optional[List[ProcessComparisonItem]] = Field(default_factory=list)
    gantt_charts: Optional[Dict[str, List[ExecutionSliceResponse]]] = Field(default_factory=dict)
    detailed_results: Optional[Dict[str, Any]] = Field(default_factory=dict)

