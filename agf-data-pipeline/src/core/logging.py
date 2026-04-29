# src/core/logging.py
"""
Centralized logging configuration for AGFI Data Pipeline.

This module configures Loguru for structured logging with:
- JSON format for production (CloudWatch friendly)
- Pretty format for development
- Automatic context binding (environment, service, request_id, etc)
-Multiple log levels based on environment

Usage:
    from src.core.logging import setup_logging, get_logger

    # Setup logging (call onde at app startup)
    setup_logging()

    # Get logger with context
    log = get_logger(__name__)
    log.info("Processing started", account_id="123456")
"""

import sys
from typing import Optional
from loguru import logger

from src.core.config import settings


def setup_logging(
    log_file: Optional[str] = None,
    rotation: str = "100 MB",
    retention: str = "30 days",
) -> None:
    """
    Configure Loguru logger based on environment settings.

    Args:
        log_file: Optional file path for logging (default None, logs only to stderr).
        rotation: Log file rotation policy. (default "100 MB").
        retention: Log file retention policy. (default "30 days").

    Note:
        - In Lambda, logs go to CloudWatch automatically via stderr.
        - In local/dev, pretty format to console.
        - In prod, JSON format for structured logging.
    """
    # Remove default logger
    logger.remove()

    # Configure base on environment
    if settings.is_dev:
        # Development: Pretty colored format
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
                "{extra}"
            ),
            level=settings.LOG_LEVEL,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    else:
        # Production/Staging: JSON format (CloudWatch friendly)
        logger.add(
            sys.stderr,
            format="{message}",
            level=settings.LOG_LEVEL,
            serialize=True, # JSON output
            backtrace=False,
            diagnose=False,
        )

    # Optional: Add file handler
    if log_file:
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message} | {extra}",
            level=settings.LOG_LEVEL,
            rotation=rotation,
            retention=retention,
            compression="zip",
            serialize=False, # Plain text for files
        )

    # Add Global context (attached to all log messages)
    logger.configure(
        extra={
            "environment": settings.ENVIRONMENT,
            "service": "agfi-data-pipeline",
            "aws_region": settings.AWS_REGION,
        }
    )

    logger.info(
        "Logging configured",
        level=settings.LOG_LEVEL,
        environment=settings.ENVIRONMENT,
        is_dev=settings.is_dev,
    )


def get_logger(name: str):
    """
    Get a logger instance with module context.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Logger instance bound with module context.

    Exemple;
        >>> log = get_logger(__name__)
        >>> log.info("Processing account", account_id="123456")
    """
    return logger.bind(module=name)

def add_request_context(request_id: str, **kwargs):
    """
    Add request-specific context to logger.

    Useful for tracing operations across multiple log statements.

    Args:
        request_id: Unique request/operation identifier
        **kwargs: Additional context fields

    Returns:
        Logger instance with request context

    Example:
        >>> log = add_request_context(
        ...     request_id="req-123456",
        ...     user_id="user-7890",
        ...     operation="btg_sync"
        ...)
        >>> log.info("Started processing")
        >>> log.error("Completed processing")
    """
    context = {"request_id": request_id, **kwargs}
    return logger.bind(**context)

def add_lambda_context(event: dict, context) -> None:
    """
    Add AWS Lambda context to logger.

    Extracts useful information from Lambda event and context objects.

    Args:
        event: Lambda event dict
        context: Lambda context object

    Example:
        >>> def lambda_handler(event, context):
        ...     add_lambda_context(event, context)
        ...     log = get_logger(__name__)
        ...     log.info("Lambda invoked")
    """
    if not context:
        return
    
    lambda_context = {}
    
    # Handle both SAM Local and real AWS Lambda context
    # SAM Local uses aws_request_id, AWS Lambda uses request_id
    if hasattr(context, 'aws_request_id'):
        lambda_context["request_id"] = context.aws_request_id
    elif hasattr(context, 'request_id'):
        lambda_context["request_id"] = context.request_id
    
    if hasattr(context, 'function_name'):
        lambda_context["function_name"] = context.function_name
    
    if hasattr(context, 'function_version'):
        lambda_context["function_version"] = context.function_version
    
    if hasattr(context, 'memory_limit_in_mb'):
        lambda_context["memory_limit_mb"] = context.memory_limit_in_mb
    
    if hasattr(context, 'get_remaining_time_in_millis'):
        try:
            lambda_context["remaining_time_ms"] = context.get_remaining_time_in_millis()
        except:
            pass

    logger.configure(extra={**logger._core.extra, **lambda_context})


# Export configured logger for convenience
__all__ = [
    "setup_logging",
    "get_logger",
    "add_request_context",
    "add_lambda_context",
    "logger"
]










