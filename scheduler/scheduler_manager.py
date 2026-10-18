"""
JobSentinel Scheduler - Scheduler Manager
Central entrypoint coordinating algorithm dispatch, input conversion,
comparative evaluation across all algorithms, and structured scheduling telemetry.
"""

import logging
from typing import List, Union, Dict, Any, Optional
from scheduler.models import (
    JobScheduleItem,
    ScheduleResult,
    AlgorithmType
)
from scheduler.fcfs import schedule_fcfs
from scheduler.sjf import schedule_sjf
from scheduler.round_robin import schedule_round_robin
from scheduler.priority import schedule_priority

logger = logging.getLogger("jobsentinel.scheduler")


class SchedulerManager:
    """
    Central coordinator for CPU scheduling operations in JobSentinel.
    """

    @staticmethod
    def normalize_job_input(raw_jobs: List[Any]) -> List[JobScheduleItem]:
        """
        Converts heterogeneous job inputs (SQLAlchemy ORM models, Pydantic models, or dicts)
        into normalized JobScheduleItem instances.
        """
        normalized: List[JobScheduleItem] = []
        for item in raw_jobs:
            if isinstance(item, JobScheduleItem):
                normalized.append(item.model_copy())
            elif isinstance(item, dict):
                normalized.append(JobScheduleItem(
                    job_id=item.get("job_id"),
                    arrival_time=float(item.get("arrival_time", 0.0)),
                    burst_time=float(item.get("burst_time", 1.0)),
                    priority=int(item.get("priority", 1)),
                    command=item.get("command", ""),
                    status=item.get("status", "PENDING")
                ))
            else:
                # Support ORM objects or generic objects with attributes
                normalized.append(JobScheduleItem(
                    job_id=getattr(item, "job_id"),
                    arrival_time=float(getattr(item, "arrival_time", 0.0)),
                    burst_time=float(getattr(item, "burst_time", 1.0)),
                    priority=int(getattr(item, "priority", 1)),
                    command=getattr(item, "command", ""),
                    status=getattr(item, "status", "PENDING")
                ))
        return normalized

    @classmethod
    def schedule(
        cls,
        jobs: List[Any],
        algorithm: Union[str, AlgorithmType],
        quantum: Optional[float] = 2.0
    ) -> ScheduleResult:
        """
        Executes the specified scheduling algorithm on the provided jobs.
        
        Supported algorithms:
        - FCFS
        - SJF
        - ROUND_ROBIN (or RR)
        - PRIORITY
        """
        normalized_jobs = cls.normalize_job_input(jobs)
        algo_str = str(algorithm.value if isinstance(algorithm, AlgorithmType) else algorithm).strip().upper()

        if algo_str == "RR":
            algo_str = "ROUND_ROBIN"

        logger.info("[Scheduler] Dispatching algorithm: %s for %d jobs", algo_str, len(normalized_jobs))

        if algo_str == "FCFS":
            result = schedule_fcfs(normalized_jobs)
        elif algo_str == "SJF":
            result = schedule_sjf(normalized_jobs)
        elif algo_str in ("ROUND_ROBIN", "RR"):
            actual_quantum = float(quantum) if quantum is not None and quantum > 0 else 2.0
            result = schedule_round_robin(normalized_jobs, quantum=actual_quantum)
        elif algo_str == "PRIORITY":
            result = schedule_priority(normalized_jobs)
        else:
            raise ValueError(f"Unsupported scheduling algorithm: '{algorithm}'. Allowed: FCFS, SJF, ROUND_ROBIN, PRIORITY")

        logger.info(
            "[Scheduler] %s complete: Avg WT=%.2fs | Avg TAT=%.2fs | Avg RT=%.2fs",
            algo_str,
            result.average_waiting_time,
            result.average_turnaround_time,
            result.average_response_time
        )
        return result

    @classmethod
    def compare_algorithms(
        cls,
        jobs: List[Any],
        quantum: float = 2.0
    ) -> Dict[str, Any]:
        """
        Executes all four algorithms on the exact same dataset to compare efficiency metrics:
        - Average Waiting Time
        - Average Turnaround Time
        - Average Response Time
        - Throughput
        """
        algorithms = [
            ("FCFS", None),
            ("SJF", None),
            ("ROUND_ROBIN", quantum),
            ("PRIORITY", None)
        ]

        normalized_jobs = cls.normalize_job_input(jobs)
        comparison_summary = []
        detailed_results = {}
        gantt_charts = {}

        # Initialize process-level comparison structure
        process_map = {}
        for j in normalized_jobs:
            jid_str = str(j.job_id)
            if jid_str not in process_map:
                process_map[jid_str] = {
                    "job_id": j.job_id,
                    "command": j.command or "",
                    "arrival_time": round(j.arrival_time, 2),
                    "burst_time": round(j.burst_time, 2),
                    "priority": j.priority,
                    "algorithms": {}
                }

        for algo_name, q in algorithms:
            res = cls.schedule(jobs, algo_name, quantum=q)
            res_dict = res.to_dict()
            detailed_results[algo_name] = res_dict
            gantt_charts[algo_name] = res_dict.get("execution_slices", [])

            # Map per-process metrics under this algorithm
            for item in res_dict.get("jobs", []):
                jid_str = str(item.get("job_id"))
                if jid_str in process_map:
                    process_map[jid_str]["algorithms"][algo_name] = {
                        "order": item.get("execution_order"),
                        "start_time": item.get("start_time"),
                        "completion_time": item.get("completion_time"),
                        "waiting_time": item.get("waiting_time"),
                        "turnaround_time": item.get("turnaround_time"),
                        "response_time": item.get("response_time")
                    }

            comparison_summary.append({
                "algorithm": algo_name,
                "average_waiting_time": round(res.average_waiting_time, 2),
                "average_turnaround_time": round(res.average_turnaround_time, 2),
                "average_response_time": round(res.average_response_time, 2),
                "throughput": round(res.throughput, 4),
                "cpu_utilization": round(res.cpu_utilization, 2)
            })

        # Rank algorithms by average waiting time (lowest is best)
        ranked = sorted(comparison_summary, key=lambda x: x["average_waiting_time"])
        best_algo = ranked[0]["algorithm"] if ranked else "N/A"

        # Sort processes by arrival time then job ID
        process_comparison = list(process_map.values())
        process_comparison.sort(key=lambda p: (p["arrival_time"], str(p["job_id"])))

        return {
            "total_jobs": len(normalized_jobs),
            "quantum_used_for_rr": quantum,
            "comparison_table": comparison_summary,
            "recommended_algorithm": best_algo,
            "process_comparison": process_comparison,
            "gantt_charts": gantt_charts,
            "detailed_results": detailed_results
        }
