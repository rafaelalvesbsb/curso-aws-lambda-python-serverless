"""
SQS Message Processor Lambda Handler

Processes messages from SQS queue containing BTG report download URLs.
Downloads the file from BTG API and saves to S3 raw data layer.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

import boto3
import httpx
from pydantic import ValidationError

# Imports from Layer
from src.core.logging import setup_logging, get_logger, add_lambda_context
from src.models.webhook import SQSMessagePayload


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for SQS message processing.

    Flow:
        1. Receive batch of messages from SQS
        2. For each message:
           a. Parse and validate payload
           b. Download file from BTG API
           c. Upload to S3 raw layer
           d. Delete message from SQS
        3. Return batch results

    Args:
        event: SQS event containing batch of messages
        context: Lambda context object

    Returns:
        Batch processing results
    """
    # Setup logging
    setup_logging()
    add_lambda_context(event, context)
    log = get_logger(__name__)

    records = event.get('Records', [])
    log.info(
        "SQS batch received",
        batch_size=len(records)
    )

    # Initialize clients
    s3_client = boto3.client('s3', endpoint_url=os.environ.get('AWS_ENDPOINT_URL'))
    bucket_name = os.environ.get('S3_BUCKET')

    if not bucket_name:
        log.error("S3_BUCKET environment variable not set")
        raise ValueError("S3_BUCKET environment variable required")

    successful = 0
    failed = 0
    batch_item_failures = []

    for record in records:
        message_id = record.get('messageId')
        receipt_handle = record.get('receiptHandle')

        log_context = log.bind(message_id=message_id)

        try:
            # Parse SQS message body
            body = json.loads(record.get('body', '{}'))
            log_context.debug("Processing SQS message", payload=body)

            # Validate with Pydantic
            try:
                message_payload = SQSMessagePayload(**body)
            except ValidationError as e:
                log_context.error(
                    "Invalid SQS message payload",
                    errors=e.errors(),
                    payload=body
                )
                # Invalid payload - skip and don't retry
                failed += 1
                continue

            log_context.info(
                "SQS message validated",
                report_type=message_payload.report_type,
                request_id=message_payload.request_id
            )

            # Download file from BTG
            log_context.info(
                "Downloading file from BTG",
                url=message_payload.download_url
            )

            file_content = download_file(
                url=message_payload.download_url,
                log=log_context
            )

            if file_content is None:
                log_context.error("Failed to download file from BTG")
                # Add to batch failures for retry
                batch_item_failures.append({"itemIdentifier": message_id})
                failed += 1
                continue

            log_context.info(
                "File downloaded successfully",
                size_bytes=len(file_content)
            )

            # Generate S3 key
            timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H%M%S")
            s3_key = f"raw/btg/{message_payload.report_type}/{timestamp}.{message_payload.file_format}"

            # Upload to S3
            log_context.info(
                "Uploading to S3",
                bucket=bucket_name,
                key=s3_key
            )

            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=file_content,
                Metadata={
                    'report_type': message_payload.report_type,
                    'request_id': message_payload.request_id or '',
                    'source': 'btg_webhook',
                    'file_format': message_payload.file_format
                }
            )

            log_context.info(
                "File saved to S3 successfully",
                s3_uri=f"s3://{bucket_name}/{s3_key}",
                size_bytes=len(file_content)
            )

            successful += 1

        except Exception as e:
            log_context.error(
                "Error processing message",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            # Add to batch failures for retry
            batch_item_failures.append({"itemIdentifier": message_id})
            failed += 1

    log.info(
        "Batch processing complete",
        total=len(records),
        successful=successful,
        failed=failed
    )

    # Return batch item failures for partial batch failure handling
    # SQS will only retry the failed messages
    return {
        "batchItemFailures": batch_item_failures
    }


def download_file(url: str, log) -> bytes | None:
    """
    Download file from URL using httpx.

    Args:
        url: URL to download from
        log: Logger instance with context

    Returns:
        File content as bytes, or None if download failed
    """
    # In local/LocalStack environments the Lambda container has its SSL traffic
    # intercepted by LocalStack, whose self-signed cert does not match external
    # hostnames. Disable verification when AWS_ENDPOINT_URL is set (local only).
    is_local = bool(os.environ.get('AWS_ENDPOINT_URL'))
    try:
        with httpx.Client(timeout=300.0, verify=not is_local) as client:  # 5 minute timeout
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()

            content_length = response.headers.get('content-length')
            log.debug(
                "HTTP response received",
                status_code=response.status_code,
                content_type=response.headers.get('content-type'),
                content_length=content_length
            )

            return response.content

    except httpx.HTTPStatusError as e:
        log.error(
            "HTTP error downloading file",
            status_code=e.response.status_code,
            error=str(e)
        )
        return None

    except httpx.RequestError as e:
        log.error(
            "Request error downloading file",
            error=str(e),
            error_type=type(e).__name__
        )
        return None

    except Exception as e:
        log.error(
            "Unexpected error downloading file",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        return None
