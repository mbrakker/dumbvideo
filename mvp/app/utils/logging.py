"""
Structured Logging System

Implements JSON logging with context tracking
"""

import logging
import structlog
from datetime import datetime
import os
import json
from typing import Dict, Any

def configure_logging(log_level: str = "INFO", log_file: str = None):
    """Configure structured logging system"""
    # Base logging configuration
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(message)s",
        handlers=[
            logging.StreamHandler(),
        ]
    )

    # Add file handler if specified
    handlers = [logging.StreamHandler()]
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(handlers),
        cache_logger_on_first_use=False,
    )

    # Set up global logger
    logger = structlog.get_logger()
    return logger

def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a named logger instance"""
    return structlog.get_logger(name)

def log_event(
    logger: structlog.BoundLogger,
    event_type: str,
    message: str,
    context: Dict[str, Any] = None,
    level: str = "info"
):
    """Log a structured event with context"""
    log_context = context or {}
    log_context.update({
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
    })

    log_method = getattr(logger, level.lower())
    log_method(message, **log_context)

# Configure default logger
logger = configure_logging()

if __name__ == "__main__":
    # Test logging
    test_logger = get_logger("test")
    test_logger.info("Logging system initialized", module="logging", status="ready")
    test_logger.debug("Debug message", details={"key": "value"})
    test_logger.warning("Warning message", severity="medium")
