"""
Unit tests for webhook_receiver Lambda function.

Tests cover:
- API Gateway event parsing
- Payload validation
- SQS message publishing
- Error handling (invalid JSON, missing fields, SQS failures)
- HTTP response formatting
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from src.aws.webhook_receiver import (
    BTGWebhookPayload,
    SQSMessage,
    create_response,
    extract_request_id,
    extract_source_ip,
    lambda_handler,
    publish_to_sqs,
    health_check_handler,
)


# ====================================================================
# FIXTURES
# ====================================================================

@pytest.fixture
def mock_sqs_queue_url(monkeypatch):
    """Mock SQS_QUEUE_URL environment variable."""
    monkeypatch.setenv("SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/btg-webhooks")


@pytest.fixture
def valid_webhook_payload():
    """Valid BTG webhook payload."""
    return {
        "event": "data_ready",
        "report_type": "account_base",
        "timestamp": "2024-01-01T12:00:00Z",
        "data": {
            "record_count": 1500,
            "file_url": "https://btg.example.com/reports/12345"
        },
        "account_id": "ACC123",
        "partner_id": "PARTNER456"
    }


@pytest.fixture
def api_gateway_event(valid_webhook_payload):
    """Valid API Gateway POST event."""
    return {
        "httpMethod": "POST",
        "body": json.dumps(valid_webhook_payload),
        "headers": {
            "Content-Type": "application/json",
            "X-Forwarded-For": "1.2.3.4"
        },
        "requestContext": {
            "requestId": "test-request-123",
            "identity": {
                "sourceIp": "1.2.3.4"
            }
        }
    }


@pytest.fixture
def mock_lambda_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.function_name = "btg-webhook-receiver"
    context.function_version = "1"
    context.aws_request_id = "test-request-123"
    return context


# ====================================================================
# PYDANTIC MODEL TESTS
# ====================================================================

def test_btg_webhook_payload_valid(valid_webhook_payload):
    """Test BTGWebhookPayload with valid data."""
    payload = BTGWebhookPayload(**valid_webhook_payload)

    assert payload.event == "data_ready"
    assert payload.report_type == "account_base"
    assert payload.timestamp == "2024-01-01T12:00:00Z"
    assert payload.data["record_count"] == 1500
    assert payload.account_id == "ACC123"
    assert payload.partner_id == "PARTNER456"


def test_btg_webhook_payload_minimal():
    """Test BTGWebhookPayload with only required fields."""
    payload = BTGWebhookPayload(event="position_updated")

    assert payload.event == "position_updated"
    assert payload.report_type is None
    assert payload.timestamp is None
    assert payload.data is None


def test_btg_webhook_payload_invalid_event():
    """Test BTGWebhookPayload rejects invalid event types."""
    with pytest.raises(ValidationError) as exc_info:
        BTGWebhookPayload(event="invalid_event_type")

    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert "Invalid event type" in str(errors[0]["ctx"]["error"])


def test_sqs_message_creation(valid_webhook_payload):
    """Test SQSMessage creation."""
    timestamp = datetime.now(timezone.utc).isoformat()

    message = SQSMessage(
        event_type="btg_webhook",
        payload=valid_webhook_payload,
        timestamp=timestamp,
        source_ip="1.2.3.4",
        request_id="req-123"
    )

    assert message.event_type == "btg_webhook"
    assert message.payload == valid_webhook_payload
    assert message.source_ip == "1.2.3.4"
    assert message.request_id == "req-123"


# ====================================================================
# HELPER FUNCTION TESTS
# ====================================================================

def test_create_response_success():
    """Test create_response with success status."""
    response = create_response(
        200,
        {"status": "success", "message": "OK"}
    )

    assert response["statusCode"] == 200
    assert "Content-Type" in response["headers"]
    assert response["headers"]["Content-Type"] == "application/json"

    body = json.loads(response["body"])
    assert body["status"] == "success"
    assert body["message"] == "OK"


def test_create_response_error():
    """Test create_response with error status."""
    response = create_response(
        400,
        {"error": "Bad Request", "message": "Invalid payload"}
    )

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "Bad Request"


def test_create_response_custom_headers():
    """Test create_response with custom headers."""
    custom_headers = {"X-Custom-Header": "custom-value"}

    response = create_response(
        200,
        {"status": "ok"},
        headers=custom_headers
    )

    assert response["headers"]["X-Custom-Header"] == "custom-value"
    assert "Content-Type" in response["headers"]  # Default header still present


def test_extract_source_ip_from_request_context(api_gateway_event):
    """Test extract_source_ip from requestContext."""
    source_ip = extract_source_ip(api_gateway_event)
    assert source_ip == "1.2.3.4"


def test_extract_source_ip_from_header():
    """Test extract_source_ip from X-Forwarded-For header."""
    event = {
        "headers": {
            "X-Forwarded-For": "5.6.7.8, 1.2.3.4"
        }
    }

    source_ip = extract_source_ip(event)
    assert source_ip == "5.6.7.8"  # First IP in comma-separated list


def test_extract_source_ip_case_insensitive():
    """Test extract_source_ip with lowercase header."""
    event = {
        "headers": {
            "x-forwarded-for": "9.10.11.12"
        }
    }

    source_ip = extract_source_ip(event)
    assert source_ip == "9.10.11.12"


def test_extract_source_ip_missing():
    """Test extract_source_ip when IP is not available."""
    event = {"headers": {}}

    source_ip = extract_source_ip(event)
    assert source_ip is None


def test_extract_request_id(api_gateway_event):
    """Test extract_request_id from requestContext."""
    request_id = extract_request_id(api_gateway_event)
    assert request_id == "test-request-123"


def test_extract_request_id_missing():
    """Test extract_request_id when not available."""
    event = {}

    request_id = extract_request_id(event)
    assert request_id is None


# ====================================================================
# SQS PUBLISHING TESTS
# ====================================================================

def test_publish_to_sqs_success(mock_sqs_queue_url, valid_webhook_payload):
    """Test successful SQS message publishing."""
    timestamp = datetime.now(timezone.utc).isoformat()

    message = SQSMessage(
        event_type="btg_webhook",
        payload=valid_webhook_payload,
        timestamp=timestamp,
        source_ip="1.2.3.4",
        request_id="req-123"
    )

    with patch("src.aws.webhook_receiver.sqs_client") as mock_sqs:
        mock_sqs.send_message.return_value = {
            "MessageId": "msg-123-456"
        }

        success = publish_to_sqs(message)

        assert success is True
        mock_sqs.send_message.assert_called_once()

        call_args = mock_sqs.send_message.call_args
        assert call_args.kwargs["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123456789012/btg-webhooks"
        assert "MessageBody" in call_args.kwargs
        assert "MessageAttributes" in call_args.kwargs


def test_publish_to_sqs_no_queue_url(monkeypatch, valid_webhook_payload):
    """Test publish_to_sqs fails when SQS_QUEUE_URL is not set."""
    monkeypatch.delenv("SQS_QUEUE_URL", raising=False)

    # Need to reload module to pick up env change
    import importlib
    import src.aws.webhook_receiver
    importlib.reload(src.aws.webhook_receiver)

    message = SQSMessage(
        event_type="btg_webhook",
        payload=valid_webhook_payload,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    with pytest.raises(ValueError) as exc_info:
        src.aws.webhook_receiver.publish_to_sqs(message)

    assert "SQS_QUEUE_URL environment variable is not set" in str(exc_info.value)


def test_publish_to_sqs_client_error(mock_sqs_queue_url, valid_webhook_payload):
    """Test publish_to_sqs handles SQS client errors."""
    message = SQSMessage(
        event_type="btg_webhook",
        payload=valid_webhook_payload,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    with patch("src.aws.webhook_receiver.sqs_client") as mock_sqs:
        mock_sqs.send_message.side_effect = Exception("SQS error")

        success = publish_to_sqs(message)

        assert success is False


# ====================================================================
# LAMBDA HANDLER TESTS
# ====================================================================

def test_lambda_handler_success(
    api_gateway_event,
    mock_lambda_context,
    mock_sqs_queue_url
):
    """Test successful webhook processing."""
    with patch("src.aws.webhook_receiver.sqs_client") as mock_sqs:
        mock_sqs.send_message.return_value = {"MessageId": "msg-123"}

        response = lambda_handler(api_gateway_event, mock_lambda_context)

        assert response["statusCode"] == 200

        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert body["event"] == "data_ready"

        # Verify SQS was called
        mock_sqs.send_message.assert_called_once()


def test_lambda_handler_invalid_method(
    api_gateway_event,
    mock_lambda_context,
    mock_sqs_queue_url
):
    """Test handler rejects non-POST requests."""
    api_gateway_event["httpMethod"] = "GET"

    response = lambda_handler(api_gateway_event, mock_lambda_context)

    assert response["statusCode"] == 405

    body = json.loads(response["body"])
    assert body["error"] == "Method Not Allowed"


def test_lambda_handler_empty_body(
    mock_lambda_context,
    mock_sqs_queue_url
):
    """Test handler rejects empty request body."""
    event = {
        "httpMethod": "POST",
        "body": None,
        "headers": {}
    }

    response = lambda_handler(event, mock_lambda_context)

    assert response["statusCode"] == 400

    body = json.loads(response["body"])
    assert body["error"] == "Bad Request"
    assert "body is required" in body["message"]


def test_lambda_handler_invalid_json(
    mock_lambda_context,
    mock_sqs_queue_url
):
    """Test handler rejects invalid JSON."""
    event = {
        "httpMethod": "POST",
        "body": "not valid json {{{",
        "headers": {}
    }

    response = lambda_handler(event, mock_lambda_context)

    assert response["statusCode"] == 400

    body = json.loads(response["body"])
    assert body["error"] == "Bad Request"
    assert "Invalid JSON" in body["message"]


def test_lambda_handler_invalid_payload_structure(
    mock_lambda_context,
    mock_sqs_queue_url
):
    """Test handler rejects payload with invalid structure."""
    event = {
        "httpMethod": "POST",
        "body": json.dumps({
            "event": "invalid_event_type",  # Invalid event
            "some_field": "value"
        }),
        "headers": {}
    }

    response = lambda_handler(event, mock_lambda_context)

    assert response["statusCode"] == 400

    body = json.loads(response["body"])
    assert body["error"] == "Bad Request"
    assert "Invalid payload structure" in body["message"]
    assert "details" in body


def test_lambda_handler_sqs_failure(
    api_gateway_event,
    mock_lambda_context,
    mock_sqs_queue_url
):
    """Test handler when SQS publish fails."""
    with patch("src.aws.webhook_receiver.sqs_client") as mock_sqs:
        mock_sqs.send_message.side_effect = Exception("SQS error")

        response = lambda_handler(api_gateway_event, mock_lambda_context)

        assert response["statusCode"] == 500

        body = json.loads(response["body"])
        assert body["error"] == "Internal Server Error"


def test_lambda_handler_base64_encoded_body(
    valid_webhook_payload,
    mock_lambda_context,
    mock_sqs_queue_url
):
    """Test handler with base64 encoded body."""
    import base64

    encoded_body = base64.b64encode(
        json.dumps(valid_webhook_payload).encode("utf-8")
    ).decode("utf-8")

    event = {
        "httpMethod": "POST",
        "body": encoded_body,
        "isBase64Encoded": True,
        "headers": {}
    }

    with patch("src.aws.webhook_receiver.sqs_client") as mock_sqs:
        mock_sqs.send_message.return_value = {"MessageId": "msg-123"}

        response = lambda_handler(event, mock_lambda_context)

        assert response["statusCode"] == 200


# ====================================================================
# HEALTH CHECK TESTS
# ====================================================================

def test_health_check_handler(mock_lambda_context):
    """Test health check endpoint."""
    event = {}

    response = health_check_handler(event, mock_lambda_context)

    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert body["status"] == "healthy"
    assert body["service"] == "btg-webhook-receiver"
    assert "timestamp" in body


# ====================================================================
# INTEGRATION TEST
# ====================================================================

@pytest.mark.integration
def test_full_webhook_flow_integration(
    api_gateway_event,
    mock_lambda_context,
    mock_sqs_queue_url
):
    """
    Integration test for complete webhook flow.

    Tests:
    - Event parsing
    - Validation
    - SQS publishing
    - Response formatting
    """
    with patch("src.aws.webhook_receiver.sqs_client") as mock_sqs:
        mock_sqs.send_message.return_value = {"MessageId": "msg-integration-123"}

        response = lambda_handler(api_gateway_event, mock_lambda_context)

        # Verify response
        assert response["statusCode"] == 200
        assert "Content-Type" in response["headers"]

        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert body["event"] == "data_ready"

        # Verify SQS call
        mock_sqs.send_message.assert_called_once()

        call_kwargs = mock_sqs.send_message.call_args.kwargs
        assert call_kwargs["QueueUrl"] == "https://sqs.us-east-1.amazonaws.com/123456789012/btg-webhooks"

        # Verify message body structure
        message_body = json.loads(call_kwargs["MessageBody"])
        assert message_body["event_type"] == "btg_webhook"
        assert "payload" in message_body
        assert "timestamp" in message_body
        assert message_body["payload"]["event"] == "data_ready"

        # Verify message attributes
        assert "MessageAttributes" in call_kwargs
        assert "event_type" in call_kwargs["MessageAttributes"]
        assert "timestamp" in call_kwargs["MessageAttributes"]
