"""
AGF AWS Utilities

AWS utilities for S3, SQS, Lambda and other AWS services.
Provides S3 client for data lake operations with partitioned data structure.
"""

__version__ = "0.1.0"

from .s3 import S3Client
from .exceptions import (
    AWSError,
    AWSS3Error,
    S3ObjectNotFoundError,
    S3PermissionError,
    S3UploadError,
    S3DownloadError,
    S3PartitionError,
    AWSSQSError,
    SQSPublishError,
    SQSReceiveError,
    AWSLambdaError,
    LambdaInvocationError,
    AWSConfigurationError,
    AWSAuthenticationError,
)

__all__ = [
    "S3Client",
    "AWSError",
    "AWSS3Error",
    "S3ObjectNotFoundError",
    "S3PermissionError",
    "S3UploadError",
    "S3DownloadError",
    "S3PartitionError",
    "AWSSQSError",
    "SQSPublishError",
    "SQSReceiveError",
    "AWSLambdaError",
    "LambdaInvocationError",
    "AWSConfigurationError",
    "AWSAuthenticationError",
]
