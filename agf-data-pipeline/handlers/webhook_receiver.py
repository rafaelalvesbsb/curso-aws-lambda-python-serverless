"""
BTG Webhook Receiver Lambda Handler

Receives webhook callbacks from BTG API when reports are ready for download.
Validates the payload and enqueues it to SQS for asynchronous processing.
"""

import json
import os
from typing import Any, Dict

import boto3
from pydantic import ValidationError

# Imports from Layer
from src.core.logging import setup_logging, get_logger, add_lambda_context
from src.models.webhook import BTGWebhookPayload, SQSMessagePayload


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for BTG webhook receiver.

    Flow:
        1. Receive webhook POST from BTG API
        2. Validate payload with Pydantic
        3. Send message to SQS queue
        4. Return 200 OK to BTG

    Args:
        event: API Gateway event containing webhook payload
        context: Lambda context object

    Returns:
        API Gateway response (200 OK or error)
    """
    # Setup logging
    setup_logging()
    add_lambda_context(event, context)
    log = get_logger(__name__)

    # API GW v2 usa rawPath/requestContext.http; v1 usa path/httpMethod
    path = event.get('rawPath') or event.get('path', '')
    method = (event.get('requestContext', {}).get('http', {}).get('method')
              or event.get('httpMethod', ''))
    source_ip = (event.get('requestContext', {}).get('http', {}).get('sourceIp')
                 or event.get('requestContext', {}).get('identity', {}).get('sourceIp'))

    log.info(
        "Webhook received",
        path=path,
        method=method,
        source_ip=source_ip
    )

    try:
        # Extract report type from URL path
        # Path format: /webhook/rm-reports-account-base
        report_type = path.split('/')[-1] if '/' in path else 'unknown'

        log.debug("Extracted report type from path", path=path, report_type=report_type)

        # Extract and parse body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)

        log.debug("Webhook payload received", payload=body)

        # Validate payload with Pydantic
        try:
            webhook_payload = BTGWebhookPayload(**body)
            log.info(
                "Webhook payload validated",
                report_type=report_type,
                file_size=webhook_payload.fileSize,
                url_expires=webhook_payload.signedURLExpirationDate
            )
        except ValidationError as e:
            log.error(
                "Invalid webhook payload",
                errors=e.errors(),
                payload=body
            )
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid webhook payload',
                    'details': e.errors()
                })
            }

        # Check if BTG reported errors for this report
        if webhook_payload.has_errors:
            log.error(
                "BTG reported errors in webhook",
                errors=webhook_payload.errors,
                report_type=report_type
            )
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'message': 'Report generation failed',
                    'errors': webhook_payload.errors
                })
            }

        # Resolve download URL (works for both flat and wrapped payloads)
        download_url = webhook_payload.download_url
        if not download_url:
            log.error("No download URL in webhook payload", payload=body)
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing download URL in webhook payload'})
            }

        # Determine file format from URL (ignore query parameters)
        url_path = download_url.split('?')[0]  # Remove query parameters
        file_format = "csv" if url_path.endswith('.csv') else "parquet"

        # Create SQS message payload
        sqs_payload = SQSMessagePayload(
            report_type=report_type,
            download_url=download_url,
            request_id=None,  # BTG doesn't send this in webhook
            file_format=file_format
        )

        # Send to SQS
        queue_url = os.environ.get('SQS_QUEUE_URL')
        if not queue_url:
            log.error("SQS_QUEUE_URL environment variable not set")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'SQS queue not configured'})
            }

        aws_endpoint_url = os.environ.get('AWS_ENDPOINT_URL')

        # boto3 SQS usa o QueueUrl como URL HTTP real da requisição, ignorando o
        # endpoint_url do cliente. Dentro do container Lambda no LocalStack,
        # "localhost.localstack.cloud" resolve para 127.0.0.1 (o próprio container),
        # causando timeout silencioso de ~20s. Normalizamos para o host interno.
        if aws_endpoint_url and queue_url:
            from urllib.parse import urlparse
            parsed = urlparse(queue_url)
            # Extrai só o path: /000000000000/agfi-sync-queue-dev
            queue_url = f"{aws_endpoint_url.rstrip('/')}{parsed.path}"
            log.debug("Queue URL normalizado para endpoint interno", queue_url=queue_url)

        # Configure boto3 client for LocalStack
        sqs_config = {
            'endpoint_url': aws_endpoint_url,
            'region_name': os.environ.get('AWS_REGION', 'us-east-1')
        }

        sqs_client = boto3.client('sqs', **sqs_config)

        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=sqs_payload.model_dump_json(),
            MessageAttributes={
                'report_type': {
                    'StringValue': report_type,
                    'DataType': 'String'
                }
            }
        )

        log.info(
            "Message sent to SQS",
            message_id=response['MessageId'],
            report_type=report_type,
            queue_url=queue_url
        )

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Webhook processed successfully',
                'report_type': report_type,
                'queued': True,
                'message_id': response['MessageId']
            })
        }

    except json.JSONDecodeError as e:
        log.error("Failed to parse JSON body", error=str(e))
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }

    except Exception as e:
        log.error(
            "Unexpected error processing webhook",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }
