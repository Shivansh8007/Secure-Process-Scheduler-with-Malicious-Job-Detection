from fastapi import APIRouter
from backend.app.api.v1.jobs import router as jobs_router
from backend.app.api.v1.scheduler import router as scheduler_router
from backend.app.api.v1.worker import router as worker_router
from backend.app.api.v1.history import router as history_router
from backend.app.api.v1.audit import router as audit_router

api_v1_router = APIRouter()

api_v1_router.include_router(jobs_router)
api_v1_router.include_router(scheduler_router)
api_v1_router.include_router(worker_router)
api_v1_router.include_router(history_router)
api_v1_router.include_router(audit_router)
