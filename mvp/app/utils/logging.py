"""
Structured Logging System

Implements JSON logging with context tracking
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

DEFAULT_LOG_LEVEL = "INFO"


def _ensure_default_context(logger: structlog.types.WrappedLogger, method_name: str, event_dict: Dict[str, Any]):
    """
    Add mandatory context fields if they are missing.
    """
    event_dict.setdefault("run_id", "unknown")
    event_dict.setdefault("task_id", "unknown")
    event_dict.setdefault("span_id", "unknown")
    return event_dict


def configure_logging(log_level: str = DEFAULT_LOG_LEVEL, log_file: Optional[str] = None) -> structlog.BoundLogger:
    """Configure structured logging system with a single handler pipeline."""
    handlers = [logging.StreamHandler()]
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(message)s",
        handlers=handlers,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _ensure_default_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    return structlog.get_logger()


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a named logger instance"""
    return structlog.get_logger(name)


def bind_context(run_id: Optional[str] = None, task_id: Optional[str] = None, span_id: Optional[str] = None, **kwargs):
    """
    Bind contextual identifiers so every log line carries run/task/span information.
    """
    context: Dict[str, Any] = {}
    if run_id is not None:
        context["run_id"] = run_id
    if task_id is not None:
        context["task_id"] = task_id
    if span_id is not None:
        context["span_id"] = span_id
    context.update(kwargs)
    structlog.contextvars.bind_contextvars(**context)


def log_event(
    logger: structlog.BoundLogger,
    role: str,
    event_type: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    level: str = "info",
):
    """Log a structured event with mandatory context and role labeling."""
    log_context = context.copy() if context else {}
    log_context.update(
        {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "role": role,
        }
    )

    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, **log_context)


# Configure default logger
logger = configure_logging()


if __name__ == "__main__":
    # Test logging
    bind_context(run_id="demo", task_id="logging_smoke", span_id="test-span")
    test_logger = get_logger("test")
    test_logger.info("Logging system initialized", module="logging", status="ready")
    log_event(test_logger, role="utility", event_type="demo", message="Structured logging ready", context={"status": "ok"})
