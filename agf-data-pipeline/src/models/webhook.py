# src/models/webhook.py
"""
Data models for BTG webhook payloads.

BTG sends payloads in two distinct formats:

Format A — Wrapped (most endpoints):
    {
        "errors": null,                          # or a list of error dicts
        "response": {
            "accountNumber": null,
            "fileSize": 3445368,
            "url": "https://...",
            "signedURLExpirationDate": "2026-02-06T07:35:40Z",
            "lastModified": "2026-02-05T10:22:01Z"
        }
    }

Format B — Flat (office-informations-by-partner):
    {
        "url": "https://...",
        "fileSize": 3096,
        "filters": {...},
        "signedURLExpirationDate": "...",
        "lastModified": "..."
    }

Format A with errors (position-history-unit-price-by-partner-v2):
    {
        "errors": [{"code": 400, "message": "Invalid account number: "}],
        "response": {
            "accountNumber": "",
            "fileSize": null,
            "url": null,
            "signedURLExpirationDate": null,
            "lastModified": null
        }
    }
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, HttpUrl, model_validator


class BTGWebhookResponse(BaseModel):
    """
    Response object inside BTG webhook payload (Format A).

    All download-related fields are Optional because BTG sends null
    values when report generation fails (errors list is non-empty).
    """
    accountNumber: Optional[str] = Field(
        None,
        description="Account number associated with the report"
    )

    fileSize: Optional[int] = Field(
        None,
        description="Size of the file in bytes",
        ge=0
    )

    url: Optional[HttpUrl] = Field(
        None,
        description="Signed S3 URL to download the report file"
    )

    signedURLExpirationDate: Optional[datetime] = Field(
        None,
        description="When the signed download URL expires"
    )

    lastModified: Optional[datetime] = Field(
        None,
        description="When the report file was last modified"
    )


class BTGWebhookPayload(BaseModel):
    """
    Payload received from BTG webhook when a report is ready (or failed).

    Handles both wrapped (Format A) and flat (Format B) payloads via
    model_validator. After validation, the following fields are always set:
        - errors:   None | list of error dicts
        - response: BTGWebhookResponse | None (None only for flat format
                    payloads that have no 'response' key)
        - url:      populated from response.url OR from flat root-level url
        - fileSize: populated from response.fileSize OR from flat root-level fileSize
    """

    # Format A fields
    errors: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = Field(
        None,
        description="Error information if report generation failed. "
                    "BTG may send a list of error dicts or null."
    )

    response: Optional[BTGWebhookResponse] = Field(
        None,
        description="Report response with download URL and metadata (Format A)."
    )

    # Format B / convenience accessors — populated by validator
    url: Optional[HttpUrl] = Field(
        None,
        description="Direct download URL (flat payload or extracted from response)"
    )

    fileSize: Optional[int] = Field(
        None,
        description="File size in bytes (flat payload or extracted from response)"
    )

    signedURLExpirationDate: Optional[datetime] = Field(
        None,
        description="URL expiration (flat payload or extracted from response)"
    )

    lastModified: Optional[datetime] = Field(
        None,
        description="Last modified date (flat payload or extracted from response)"
    )

    @model_validator(mode="before")
    @classmethod
    def normalise_payload(cls, data: Any) -> Any:
        """
        Normalise both BTG payload formats into a consistent shape.

        - Format B (flat): no 'response' key but has 'url' / 'fileSize' at root.
          We leave the flat fields as-is; response stays None.
        - Format A (wrapped): has 'response' dict. We copy url/fileSize up to
          the top level for easy access, keeping 'response' intact.
        """
        if not isinstance(data, dict):
            return data

        has_response_key = "response" in data

        if has_response_key:
            # Format A — copy convenience fields from nested response to root
            inner = data.get("response") or {}
            if isinstance(inner, dict):
                for field in ("url", "fileSize", "signedURLExpirationDate", "lastModified"):
                    if field not in data and inner.get(field) is not None:
                        data[field] = inner[field]
        # Format B — root-level url/fileSize are already present; nothing to do.

        return data

    @property
    def has_errors(self) -> bool:
        """True if BTG reported one or more errors for this report."""
        return bool(self.errors)

    @property
    def download_url(self) -> Optional[str]:
        """Resolved download URL regardless of payload format."""
        url = self.url
        if url is None and self.response is not None:
            url = self.response.url
        return str(url) if url is not None else None

    model_config = {
        "extra": "allow",
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Format A — success",
                    "value": {
                        "errors": None,
                        "response": {
                            "accountNumber": None,
                            "fileSize": 3445368,
                            "url": "https://invest-reports-prd.s3.sa-east-1.amazonaws.com/report.csv",
                            "signedURLExpirationDate": "2026-02-06T07:35:40Z",
                            "lastModified": "2026-02-05T10:22:01Z"
                        }
                    }
                },
                {
                    "title": "Format A — errors",
                    "value": {
                        "errors": [{"code": 400, "message": "Invalid account number: "}],
                        "response": {
                            "accountNumber": "",
                            "fileSize": None,
                            "url": None,
                            "signedURLExpirationDate": None,
                            "lastModified": None
                        }
                    }
                },
                {
                    "title": "Format B — flat (office-informations-by-partner)",
                    "value": {
                        "url": "https://invest-reports-prd.s3.sa-east-1.amazonaws.com/office.csv",
                        "fileSize": 3096,
                        "filters": {},
                        "signedURLExpirationDate": "2026-02-06T07:35:40Z",
                        "lastModified": "2026-02-05T10:22:01Z"
                    }
                }
            ]
        }
    }


class SQSMessagePayload(BaseModel):
    """
    Message payload sent to SQS queue for processing.

    This is what the data processor Lambda will receive.
    """

    report_type: str
    download_url: str
    request_id: Optional[str] = None
    file_format: str = "parquet"
    received_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "json_schema_extra": {
            "example": {
                "report_type": "rm_reports_account_base",
                "download_url": "https://api.btgpactual.com/download/abc123.parquet",
                "request_id": "req-123456",
                "file_format": "parquet",
                "received_at": "2026-01-29T14:30:00Z"
            }
        }
    }
