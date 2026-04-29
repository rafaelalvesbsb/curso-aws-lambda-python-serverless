# src/models/__init__.py

"""
Data models for AGFI Data Pipeline.

This package contains Pydantic models for:
- BTG API data structures
- HubSpot CRM objects
- Internal data models for processing
"""

# Models will be imported here as they are created
from src.models.webhook import BTGWebhookPayload, SQSMessagePayload

__all__ = [
    "BTGWebhookPayload",
    "SQSMessagePayload",
]
