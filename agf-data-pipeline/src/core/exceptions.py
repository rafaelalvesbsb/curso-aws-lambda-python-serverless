# src/core/exceptions.py

"""
Custom exceptions for AGFI Data Pipeline.

Provides a hierarchy of domain-specific exceptions for better error handling
and debugging across the pipeline.

Exception Hierarchy:
    DataPipelineException (base)
    ├── ConfigurationError
    ├── ValidationError
    ├── BTGAPIError (base)
    │   ├── BTGAuthenticationError
    │   ├── BTGRateLimitError
    │   └── BTGDataError
    ├── HubSpotAPIError (base)
    │   ├── HubSpotAuthenticationError
    │   ├── HubSpotRateLimitError
    │   ├── HubSpotDataError
    │   └── HubSpotObjectNotFoundError
    ├── S3StorageError
    ├── DatabaseError
    └── ProcessingError


Usage:
    from src.core.exceptions import BTGAPIError, ValidationError

    if not account_id:
        raise ValidationError("Account ID is required", field="account_id")

    try:
        response = btg_client.get_accounts()
    except BTGAuthenticationError as e:
        log.error("BTG auth failed", error=str(e))
        raise
"""

from typing import Any, Optional


class DataPipelineException(Exception):
    """
    Base exception for all AGFI Data Pipeline errors.

    All custom exceptions inherit from this base class for easier
    error handling and logging.

    Attributes:
        message: Human-readable error message
        details: Additional context about the error
        original_error: The original exception if this is a wrapped error
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self) -> str:
        """String representation with details."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "original_error": str(self.original_error) if self.original_error else None,
        }


# Configuration Errors
class ConfigurationError(DataPipelineException):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        details = kwargs.get("details", {})
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, details=details, **kwargs)


# Validation Errors
class ValidationError(DataPipelineException):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        super().__init__(message, details=details, **kwargs)


# BTG API Errors
class BTGAPIError(DataPipelineException):
    """Base exception for BTG API related errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if status_code:
            details["status_code"] = status_code
        if response_body:
            details["response_body"] = response_body
        super().__init__(message, details=details, **kwargs)


class BTGAuthenticationError(BTGAPIError):
    """Raised when BTG API authentication fails."""

    def __init__(self, message: str = "BTG authentication failed", **kwargs):
        super().__init__(message, **kwargs)


class BTGRateLimitError(BTGAPIError):
    """Raised when BTG API rate limit is exceeded."""

    def __init__(
        self,
        message: str = "BTG API rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(message, details=details, **kwargs)


class BTGDataError(BTGAPIError):
    """Raised when BTG API returns unexpected or invalid data."""

    def __init__(
        self,
        message: str = "Invalid data received from BTG API",
        endpoint: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if endpoint:
            details["endpoint"] = endpoint
        super().__init__(message, details=details, **kwargs)

class BTGTransientHTTPError(BTGAPIError):
    """
    Raised for transient HTTP errors that should be retried.

    This includes:
    - Connection errors
    - Timeouts (read/write/pool)
    - Server errors (5xx)
    - Temporary unavailability (e.g., "Relatório não disponível")
    """

    def __init__(
        self,
        message: str = "Transient HTTP error occurred",
        **kwargs,
    ):
        super().__init__(message, **kwargs)


#Hubspot API Errors
class HubSpotAPIError(DataPipelineException):
    """Base exception for HubSpot API related errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if status_code:
            details["status_code"] = status_code
        if response_body:
            details["response_body"] = response_body
        super().__init__(message, details=details, **kwargs)


class HubSpotAuthenticationError(HubSpotAPIError):
    """Raised when HubSpot API authentication fails."""

    def __init__(self, message: str = "HubSpot authentication failed", **kwargs):
        super().__init__(message, **kwargs)

class HubSpotRateLimitError(HubSpotAPIError):
    """Raised when the HubSpot API rate limit is exceeded."""

    def __init__(
        self,
        message: str = "HubSpot API rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(message, details=details, **kwargs)

class HubSpotDataError(HubSpotAPIError):
    """Raised when HubSpot API returns unexpected or invalid data."""

    def __init__(
        self,
        message: str = "Invalid data received from HubSpot API",
        endpoint: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if endpoint:
            details["endpoint"] = endpoint
        super().__init__(message, details=details, **kwargs)

class HubSpotObjectNotFoundError(HubSpotAPIError):
    """Raised when a requested HubSpot object is not found."""

    def __init__(
        self,
        message: str = "HubSpot object not found",
        object_type: Optional[str] = None,
        object_id: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if object_type:
            details["object_type"] = object_type
        if object_id:
            details["object_id"] = object_id
        super().__init__(message, details=details, **kwargs)


# Storage Errors
class S3StorageError(DataPipelineException):
    """Raised when S3 operations fail."""

    def __init__(
        self,
        message: str,
        bucket: Optional[str] = None,
        key: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if bucket:
            details["bucket"] = bucket
        if key:
            details["key"] = key
        if operation:
            details["operation"] = operation
        super().__init__(message, details=details, **kwargs)


# Database Errors
class DatabaseError(DataPipelineException):
    """Raised when database operations fail."""

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        table: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if query:
            details["query"] = query[:200]  # Truncate long queries
        if table:
            details["table"] = table
        super().__init__(message, details=details, **kwargs)


# Processing Errors
class ProcessingError(DataPipelineException):
    """Raised when data processing fails."""

    def __init__(
        self,
        message: str,
        step: Optional[str] = None,
        record_id: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.get("details", {})
        if step:
            details["processing_step"] = step
        if record_id:
            details["record_id"] = record_id
        super().__init__(message, details=details, **kwargs)


# Export all exceptions
__all__ = [
    "DataPipelineException",
    "ConfigurationError",
    "ValidationError",
    "BTGAPIError",
    "BTGAuthenticationError",
    "BTGRateLimitError",
    "BTGDataError",
    "BTGTransientHTTPError",
    "HubSpotAPIError",
    "HubSpotAuthenticationError",
    "HubSpotRateLimitError",
    "HubSpotDataError",
    "HubSpotObjectNotFoundError",
    "S3StorageError",
    "DatabaseError",
    "ProcessingError",
]
