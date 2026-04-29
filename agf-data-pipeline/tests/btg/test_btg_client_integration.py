"""
Integration tests for BTGClient.

These tests verify:
- OAuth2 authentication flow
- API request handling with retry logic
- Error handling (transient errors, rate limiting, etc.)
- Health check functionality

Requirements:
- BTG_CLIENT_ID and BTG_CLIENT_SECRET environment variables
- Active internet connection to BTG API
"""

import os
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from src.btg.client import BTGClient, _is_transient
from src.lambda_handler.exceptions import (
    BTGAPIError,
    BTGAuthenticationError,
    BTGRateLimitError,
    BTGTransientHTTPError,
)


# ====================================================================
# FIXTURES
# ====================================================================

@pytest.fixture
def mock_env_credentials(monkeypatch):
    """Mock BTG credentials in environment variables."""
    monkeypatch.setenv("BTG_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("BTG_CLIENT_SECRET", "test_client_secret")


@pytest.fixture
def client_with_mock_credentials(mock_env_credentials):
    """Create BTGClient with mocked credentials."""
    return BTGClient()


# ====================================================================
# UNIT TESTS - _is_transient function
# ====================================================================

def test_is_transient_with_connect_error():
    """Test that ConnectError is identified as transient."""
    exc = httpx.ConnectError("Connection failed")
    assert _is_transient(exc) is True


def test_is_transient_with_read_timeout():
    """Test that ReadTimeout is identified as transient."""
    exc = httpx.ReadTimeout("Read timeout")
    assert _is_transient(exc) is True


def test_is_transient_with_btg_transient_error():
    """Test that BTGTransientHTTPError is identified as transient."""
    exc = BTGTransientHTTPError("Temporary error")
    assert _is_transient(exc) is True


def test_is_transient_with_non_transient_error():
    """Test that regular exceptions are not identified as transient."""
    exc = ValueError("Some error")
    assert _is_transient(exc) is False


# ====================================================================
# INITIALIZATION TESTS
# ====================================================================

def test_client_initialization_with_env_vars(mock_env_credentials):
    """Test BTGClient initialization with environment variables."""
    client = BTGClient()

    assert client.client_id == "test_client_id"
    assert client.client_secret == "test_client_secret"
    assert client.base_url == "https://api.btgpactual.com"
    assert client.timeout == 30.0


def test_client_initialization_with_explicit_credentials():
    """Test BTGClient initialization with explicit credentials."""
    client = BTGClient(
        client_id="explicit_id",
        client_secret="explicit_secret",
        timeout=60.0
    )

    assert client.client_id == "explicit_id"
    assert client.client_secret == "explicit_secret"
    assert client.timeout == 60.0


def test_client_initialization_without_credentials(monkeypatch):
    """Test that initialization fails without credentials."""
    monkeypatch.delenv("BTG_CLIENT_ID", raising=False)
    monkeypatch.delenv("BTG_CLIENT_SECRET", raising=False)

    with pytest.raises(BTGAuthenticationError) as exc_info:
        BTGClient()

    assert "must be provided or set in environment" in str(exc_info.value)


def test_generate_auth_header(client_with_mock_credentials):
    """Test Basic Auth header generation."""
    auth_header = client_with_mock_credentials._generate_auth_header()

    assert auth_header.startswith("Basic ")
    # Basic auth should be base64(client_id:client_secret)
    import base64
    expected = base64.b64encode(b"test_client_id:test_client_secret").decode()
    assert auth_header == f"Basic {expected}"


# ====================================================================
# AUTHENTICATION TESTS
# ====================================================================

@pytest.mark.asyncio
async def test_authentication_success(client_with_mock_credentials):
    """Test successful OAuth2 authentication."""
    # Mock HTTP client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"access_token": "test_access_token_123"}
    mock_response.raise_for_status = MagicMock()

    with patch.object(
        client_with_mock_credentials,
        "_http_client",
        create=True
    ) as mock_http_client:
        mock_http_client.post = AsyncMock(return_value=mock_response)

        await client_with_mock_credentials._ensure_authenticated()

        assert client_with_mock_credentials._access_token == "test_access_token_123"
        assert client_with_mock_credentials._token_expiries_at is not None


@pytest.mark.asyncio
async def test_authentication_missing_token_in_header(client_with_mock_credentials):
    """Test authentication failure when access_token is missing from response header."""
    # Mock HTTP client
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {}  # No access_token header
    mock_response.raise_for_status = MagicMock()

    with patch.object(
        client_with_mock_credentials,
        "_http_client",
        create=True
    ) as mock_http_client:
        mock_http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(BTGAuthenticationError) as exc_info:
            await client_with_mock_credentials._ensure_authenticated()

        assert "No access_token in response headers" in str(exc_info.value)


@pytest.mark.asyncio
async def test_authentication_http_error(client_with_mock_credentials):
    """Test authentication failure with HTTP error."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch.object(
        client_with_mock_credentials,
        "_http_client",
        create=True
    ) as mock_http_client:
        mock_http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Auth failed",
                request=MagicMock(),
                response=mock_response
            )
        )

        with pytest.raises(BTGAuthenticationError) as exc_info:
            await client_with_mock_credentials._ensure_authenticated()

        assert "Failed to authenticate" in str(exc_info.value)


# ====================================================================
# API CALL TESTS
# ====================================================================

@pytest.mark.asyncio
async def test_call_btg_api_success(client_with_mock_credentials):
    """Test successful API call."""
    # Mock authentication
    client_with_mock_credentials._access_token = "test_token"
    client_with_mock_credentials._token_expiries_at = None

    with patch.object(
        client_with_mock_credentials,
        "_ensure_authenticated",
        new_callable=AsyncMock
    ):
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "success"}'

        with patch.object(
            client_with_mock_credentials,
            "_http_client",
            create=True
        ) as mock_http_client:
            mock_http_client.request = AsyncMock(return_value=mock_response)

            result = await client_with_mock_credentials._call_btg_api(
                "GET",
                "/test-endpoint"
            )

            assert result["status_code"] == 200
            assert "timestamp" in result


@pytest.mark.asyncio
async def test_call_btg_api_rate_limit(client_with_mock_credentials):
    """Test API call handling rate limit (429)."""
    client_with_mock_credentials._access_token = "test_token"
    client_with_mock_credentials._token_expiries_at = None

    with patch.object(
        client_with_mock_credentials,
        "_ensure_authenticated",
        new_callable=AsyncMock
    ):
        # Mock 429 response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        with patch.object(
            client_with_mock_credentials,
            "_http_client",
            create=True
        ) as mock_http_client:
            mock_http_client.request = AsyncMock(return_value=mock_response)

            with pytest.raises(BTGRateLimitError) as exc_info:
                await client_with_mock_credentials._call_btg_api(
                    "GET",
                    "/test-endpoint"
                )

            assert "Rate limit exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_call_btg_api_server_error_with_retry(client_with_mock_credentials):
    """Test API call retries on 5xx server errors."""
    client_with_mock_credentials._access_token = "test_token"
    client_with_mock_credentials._token_expiries_at = None

    with patch.object(
        client_with_mock_credentials,
        "_ensure_authenticated",
        new_callable=AsyncMock
    ):
        # First call returns 500, second call succeeds
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200

        with patch.object(
            client_with_mock_credentials,
            "_http_client",
            create=True
        ) as mock_http_client:
            mock_http_client.request = AsyncMock(
                side_effect=[mock_response_error, mock_response_success]
            )

            result = await client_with_mock_credentials._call_btg_api(
                "GET",
                "/test-endpoint"
            )

            # Should succeed after retry
            assert result["status_code"] == 200


@pytest.mark.asyncio
async def test_call_btg_api_report_not_available_retry(client_with_mock_credentials):
    """Test API call retries on 404 with 'Relatório não disponível'."""
    client_with_mock_credentials._access_token = "test_token"
    client_with_mock_credentials._token_expiries_at = None

    with patch.object(
        client_with_mock_credentials,
        "_ensure_authenticated",
        new_callable=AsyncMock
    ):
        # First call returns 404 with specific message, second call succeeds
        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404
        mock_response_404.text = "Relatório não disponível no momento"
        mock_response_404.json = MagicMock(
            return_value={"error": "Relatório não disponível"}
        )

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200

        with patch.object(
            client_with_mock_credentials,
            "_http_client",
            create=True
        ) as mock_http_client:
            mock_http_client.request = AsyncMock(
                side_effect=[mock_response_404, mock_response_success]
            )

            result = await client_with_mock_credentials._call_btg_api(
                "GET",
                "/test-endpoint"
            )

            # Should succeed after retry
            assert result["status_code"] == 200


# ====================================================================
# ENDPOINT TESTS
# ====================================================================

@pytest.mark.asyncio
async def test_rm_reports_account_base_endpoint(client_with_mock_credentials):
    """Test rm_reports_account_base endpoint."""
    with patch.object(
        client_with_mock_credentials,
        "_call_btg_api",
        new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = {"status_code": 200, "timestamp": "2024-01-01T00:00:00Z"}

        result = await client_with_mock_credentials.rm_reports_account_base()

        mock_call.assert_called_once_with(
            "GET",
            "/api-rm-reports/api/v1/rm-reports/account-base"
        )
        assert result["status_code"] == 200


@pytest.mark.asyncio
async def test_position_by_partner_endpoint(client_with_mock_credentials):
    """Test position_by_partner endpoint."""
    with patch.object(
        client_with_mock_credentials,
        "_call_btg_api",
        new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = {"status_code": 200, "timestamp": "2024-01-01T00:00:00Z"}

        result = await client_with_mock_credentials.position_by_partner()

        mock_call.assert_called_once_with(
            "GET",
            "/iaas-api-position/api/v1/position/refresh"
        )
        assert result["status_code"] == 200


@pytest.mark.asyncio
async def test_get_open_finance_position_by_account_endpoint(client_with_mock_credentials):
    """Test get_open_finance_position_by_account endpoint with account parameter."""
    with patch.object(
        client_with_mock_credentials,
        "_call_btg_api",
        new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = {"status_code": 200, "timestamp": "2024-01-01T00:00:00Z"}

        result = await client_with_mock_credentials.get_open_finance_position_by_account(
            account="12345"
        )

        mock_call.assert_called_once_with(
            "GET",
            "/iaas-investment-consolidation/api/v1/open-finance/position/12345"
        )
        assert result["status_code"] == 200


# ====================================================================
# HEALTH CHECK TESTS
# ====================================================================

@pytest.mark.asyncio
async def test_health_check_success(client_with_mock_credentials):
    """Test health check when authentication succeeds."""
    with patch.object(
        client_with_mock_credentials,
        "_ensure_authenticated",
        new_callable=AsyncMock
    ):
        result = await client_with_mock_credentials.health_check()
        assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(client_with_mock_credentials):
    """Test health check when authentication fails."""
    with patch.object(
        client_with_mock_credentials,
        "_ensure_authenticated",
        new_callable=AsyncMock,
        side_effect=BTGAuthenticationError("Auth failed")
    ):
        result = await client_with_mock_credentials.health_check()
        assert result is False


# ====================================================================
# CONTEXT MANAGER TESTS
# ====================================================================

@pytest.mark.asyncio
async def test_context_manager_usage(client_with_mock_credentials):
    """Test BTGClient as async context manager."""
    with patch.object(
        client_with_mock_credentials,
        "_ensure_authenticated",
        new_callable=AsyncMock
    ):
        async with client_with_mock_credentials as client:
            assert client._http_client is not None
            assert isinstance(client._http_client, httpx.AsyncClient)

        # After context exit, client should be closed
        # Note: We can't easily test this without accessing private attributes


# ====================================================================
# INTEGRATION TEST (requires real credentials)
# ====================================================================

@pytest.mark.skipif(
    not os.getenv("BTG_CLIENT_ID") or not os.getenv("BTG_CLIENT_SECRET"),
    reason="BTG credentials not available"
)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_authentication():
    """
    Integration test with real BTG API.

    Requires:
    - BTG_CLIENT_ID environment variable
    - BTG_CLIENT_SECRET environment variable

    Run with: pytest -m integration
    """
    async with BTGClient() as client:
        # Test authentication
        assert client._access_token is not None

        # Test health check
        is_healthy = await client.health_check()
        assert is_healthy is True
