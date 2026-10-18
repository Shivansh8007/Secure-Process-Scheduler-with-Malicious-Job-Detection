from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import settings
from backend.app.core.logging import setup_logging, logger
from backend.app.core.database import check_db_connection, init_db
from backend.app.core.exceptions import JobSentinelException
from backend.app.api.v1.router import api_v1_router
from backend.app.api.deps import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown procedures."""
    setup_logging()
    logger.info("Initializing JobSentinel Backend (Phase 2)...")
    logger.info("Environment: %s | Target Host: %s:%s", settings.APP_ENV, settings.APP_HOST, settings.APP_PORT)

    # Attempt database verification and table creation
    from backend.app.core.database import ensure_db_ready
    import backend.app.models  # ensure models are registered
    ensure_db_ready()

    yield

    logger.info("Shutting down JobSentinel Backend.")


app = FastAPI(
    title="JobSentinel API",
    description=(
        "Secure Process Scheduler with Persistent Database Queue — Phase 2 Backend.\n\n"
        "Provides job persistence in MySQL, lifecycle state transitions, "
        "Scheduler interface (Member 2), Worker interface (Member 3), "
        "Execution history, and Audit logs for Frontend (Member 4)."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Enable CORS for frontend integration (Member 4)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(JobSentinelException)
async def jobsentinel_exception_handler(request: Request, exc: JobSentinelException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.__class__.__name__, "detail": exc.message}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "ValidationError", "detail": exc.errors()}
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database error occurred: %s", str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "DatabaseError",
            "detail": "An internal database error occurred. Please check server logs for details."
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled server exception: %s", str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "InternalServerError", "detail": "An unexpected error occurred."}
    )


# Health check
@app.get("/health", tags=["Health"], summary="Health and database connectivity status")
def health_check():
    is_connected = check_db_connection()
    return {
        "status": "healthy" if is_connected else "degraded",
        "database_connected": is_connected,
        "environment": settings.APP_ENV,
        "version": "2.0.0"
    }


FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


@app.get("/", tags=["Root"], summary="API Root metadata")
def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and FRONTEND_DIR.exists():
        return RedirectResponse(url="/frontend/")
    return {
        "project": "JobSentinel",
        "description": "Secure Process Scheduler with Persistent Database Queue",
        "docs_url": "/docs",
        "health_url": "/health",
        "frontend_url": "/frontend/",
        "version": "2.0.0"
    }


# Include routes at root level (as specified in requirements) and /api/v1
app.include_router(api_v1_router)
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/dashboard/stats", tags=["Dashboard"], summary="Aggregated job metrics for dashboard")
def dashboard_stats(db = Depends(get_db)):
    """Provides summary counts across all lifecycle states for Member 4's UI."""
    from sqlalchemy import func
    from backend.app.models.job import Job
    rows = db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    stats = {
        "total": 0,
        "pending": 0,
        "scheduled": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "quarantined": 0
    }
    for status_val, count in rows:
        key = str(status_val).lower()
        if key in stats:
            stats[key] = count
        stats["total"] += count
    return stats

