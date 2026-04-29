"""
AGF BTG Pactual API Client

Unified client for BTG Pactual API with OAuth2 authentication,
retry logic, and schema validation.

Usage:
    from btg import BTGClient

    async with BTGClient() as client:
        response = await client.rm_reports_registration_data()
"""

__version__ = "0.1.0"

from .client import BTGClient
from .exceptions import (
    BTGError,
    BTGAPIError,
    BTGAuthenticationError,
    BTGRateLimitError,
    BTGDataError,
    BTGTransientHTTPError,
)

__all__ = [
    "BTGClient",
    "BTGError",
    "BTGAPIError",
    "BTGAuthenticationError",
    "BTGRateLimitError",
    "BTGDataError",
    "BTGTransientHTTPError",
]
