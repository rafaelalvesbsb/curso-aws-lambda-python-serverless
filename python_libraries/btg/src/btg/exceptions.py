# btg/src/btg/exceptions.py
"""
BTG API Exceptions.

Lightweight exception hierarchy for handling BTG API related errors.
These exceptions are library-specific and don't depend on external code.
"""

from typing import Any, Optional


class BTGError(Exception):
    """
    Base exception for BTG API errors.

    Attributes:
        message: Human-readable error message
        details: Additional context (status_code, response_body, etc.)
        original_error: Original exception if wrapped
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
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "original_error": str(self.original_error) if self.original_error else None,
        }


class BTGAPIError(BTGError):
    """Generic BTG API error."""

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
    """Authentication failed with BTG OAuth2."""

    def __init__(self, message: str = "BTG authentication failed", **kwargs):
        super().__init__(message, **kwargs)


class BTGRateLimitError(BTGAPIError):
    """Rate limit exceeded (429)."""

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
    """Data validation or parsing error."""

    def __init__(
            self,
            message: str = "Invalid data from BTG API",
            endpoint: Optional[str] = None,
            **kwargs,
    ):
        details = kwargs.get("details", {})
        if endpoint:
            details["endpoint"] = endpoint
        super().__init__(message, details=details, **kwargs)


class BTGTransientHTTPError(BTGAPIError):
    """
    Transient HTTP error that should be retried.

    Includes:
    - Connection errors
    - Timeouts
    - 5xx server errors
    - Temporary unavailability
    """

    def __init__(self, message: str = "Transient HTTP error", **kwargs):
        super().__init__(message, **kwargs)


__all__ = [
    "BTGError",
    "BTGAPIError",
    "BTGAuthenticationError",
    "BTGRateLimitError",
    "BTGDataError",
    "BTGTransientHTTPError",
]