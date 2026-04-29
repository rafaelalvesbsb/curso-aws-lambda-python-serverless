# src/aws/exceptions.py

"""
Exception hierarchy for AWS utilities library.

Provides structured exceptions for AWS operations with rich context
for debugging and error handling.
"""

from typing import Any, Optional


class AWSError(Exception):
    """
    Base exception for all AWS-related errors.

    All AWS exceptions inherit from this base class, providing consistent
    error handling and structured error information.

    Attributes:
        message: Human-readable error description
        details: Additional context about the error
        original_error: The underlying exception if this wraps another error
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
        """String representation of the error."""
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"details={self.details!r}, "
            f"original_error={self.original_error!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert exception to dictionary for logging/serialization.

        Returns:
            Dictionary with error type, message, details, and original error
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "original_error": str(self.original_error) if self.original_error else None,
        }


class AWSS3Error(AWSError):
    """Base exception for S3-related errors."""
    pass


class S3ObjectNotFoundError(AWSS3Error):
    """Raised when an S3 object cannot be found."""
    pass


class S3PermissionError(AWSS3Error):
    """Raised when there are permission issues accessing S3."""
    pass


class S3UploadError(AWSS3Error):
    """Raised when an S3 upload operation fails."""
    pass


class S3DownloadError(AWSS3Error):
    """Raised when an S3 download operation fails."""
    pass


class S3PartitionError(AWSS3Error):
    """Raised when there are issues with S3 partition operations."""
    pass


class AWSSQSError(AWSError):
    """Base exception for SQS-related errors."""
    pass


class SQSPublishError(AWSSQSError):
    """Raised when publishing a message to SQS fails."""
    pass


class SQSReceiveError(AWSSQSError):
    """Raised when receiving messages from SQS fails."""
    pass


class AWSLambdaError(AWSError):
    """Base exception for Lambda-related errors."""
    pass


class LambdaInvocationError(AWSLambdaError):
    """Raised when Lambda invocation fails."""
    pass


class AWSConfigurationError(AWSError):
    """Raised when there are AWS configuration issues."""
    pass


class AWSAuthenticationError(AWSError):
    """Raised when AWS authentication fails."""
    pass
