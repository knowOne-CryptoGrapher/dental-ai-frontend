import logging
import os
from pythonjsonlogger import jsonlogger


def configure_logging() -> None:
    """
    Configure root logger with JSON output for Cloud Logging.

    Every log line becomes a structured JSON object with at minimum:
      timestamp, level, logger, message
    plus any extra fields passed via logger.info(..., extra={...}).
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
            rename_fields={
                "levelname": "level",
                "asctime": "timestamp",
                "name": "logger",
            },
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy third-party libs; they still emit at WARNING+
    for noisy in ("uvicorn.access", "motor", "pymongo", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
