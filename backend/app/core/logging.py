import logging
import sys
from backend.app.core.config import settings


def setup_logging():
    """Configure structured logging for JobSentinel."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Silence overly verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger = logging.getLogger("jobsentinel")
    logger.info("Logging configured successfully with level: %s", settings.LOG_LEVEL)
    return logger


logger = logging.getLogger("jobsentinel")
