# src/btg/client.py

"""
BTG Pactual API Client
Unified client for all BTG API endpoints with OAuth2 authentication.
"""

import os
import uuid
import base64
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List
from loguru import logger
import httpx
from tenacity import (
    AsyncRetrying,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

from .schemas.account_information import AccountInformationRaw
from .exceptions import (
    BTGAPIError,
    BTGAuthenticationError,
    BTGRateLimitError,
    BTGDataError,
    BTGTransientHTTPError
)

def _is_transient(exc: BaseException) -> bool:
    """
    Determine if an exception is transient and should be retried.

    Retries for:
    - Connection errors
    - Timeouts (read/write/pool)
    - Explicit TransientHTTPError wrapper
    """
    if isinstance(exc, (
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.WriteError,
        httpx.PoolTimeout,
    )):
        return True
    if isinstance(exc, BTGTransientHTTPError):
        return True
    return False

class BTGClient:
    """
    Unified BTG Pactual API Client

    Handles:
    - OAuth2 authentication with automatic token refresh
    - All BTG API endpoints (15+ endpoints supported)
    - Schema validation
    - Retry logic with exponential backoff
    - Request tracking with UUIDs

    Usage:
        async with BTGClient() as client:
            # Get account information
            account = await client.get_account_information("12345")

            # Get custody position
            await client.position_by_partner()

            # Get registration data
            await client.rm_reports_registration_data()
    """

    # Token expiration buffer (refresh 5 minutes before expiration)
    TOKEN_BUFFER_SECONDS = 300

    def __init__(
        self,
        base_url: str = "https://api.btgpactual.com",
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize BTG Client.

        Args:
            base_url: BTG API base URL
            client_id: OAuth2 Client ID (defaults to BTG_CLIENT_ID env var)
            client_secret: OAuth2 client secret (defaults to BTG_CLIENT_SECRET env var)
            timeout: Request timeout in seconds
        """

        self.base_url = base_url.rstrip("/")
        self.client_id = client_id or os.getenv("BTG_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("BTG_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise BTGAuthenticationError(
                "BTG_CLIENT_ID and BTG_CLIENT_SECRET must be provided or set in environment."
            )

        self.timeout = timeout
        self._http_client: Optional[httpx.AsyncClient] = None
        self._access_token: Optional[str] = None
        self._token_expiries_at: Optional[datetime] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._http_client = httpx.AsyncClient(timeout=self.timeout)
        await self._ensure_authenticated()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._http_client:
            await self._http_client.aclose()

    def _generate_auth_header(self) -> str:
        """
        Generate Basic Auth header for OAuth2 token request.
        Format: Basic base64(client_id:client_secret)
        """
        credentials = f"{self.client_id}:{self.client_secret}"
        encode = base64.b64encode(credentials.encode("ascii")).decode("ascii")
        return f"Basic {encode}"

    async def _ensure_authenticated(self) -> None:
        """
        Ensure we have a valid access token.
        Refreshes token if expired or close to expiration.
        """
        now = datetime.utcnow()

        # Check if token exists and still valid
        if self._access_token and self._token_expiries_at:
            if now < self._token_expiries_at:
                return

        # Get a new token
        logger.info("Authenticating with BTG OAuth2...")

        auth_url = f"{self.base_url}/iaas-auth/api/v1/authorization/oauth2/accesstoken"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self._generate_auth_header(),
            "x-id-partner-request": str(uuid.uuid4())
        }

        data = {
            "grant_type": "client_credentials"
        }

        try:
            response = await self._http_client.post(
                auth_url,
                data=data,
                headers=headers,
            )
            response.raise_for_status()

            # BTG returns access_token in HEADER, not body
            access_token = response.headers.get("access_token")

            if not access_token:
                raise BTGAuthenticationError(
                    "No access_token in response headers"
                )

            self._access_token = access_token

            # BTG tokens typically expire in 3600 seconds (1 hour)
            # Set expiration with buffer
            expires_in = 3600
            self._token_expiries_at = now + timedelta(
                seconds=expires_in - self.TOKEN_BUFFER_SECONDS
            )

            logger.info(
                f"Authenticated successful. Token expires at {self._token_expiries_at}"
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Authentication failed: {e.response.status_code} - {e.response.text}"
            )

            raise BTGAuthenticationError(
                f"Failed to authenticate: {e.response.status_code}"
            ) from e
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise BTGAuthenticationError(
                f"Authentication error: {str(e)}"
            ) from e

    async def _call_btg_api(
            self,
            method: str,
            endpoint: str,
            *,
            return_body: bool = False,
            **kwargs
    ) -> Dict[str, Any]:
        """
        Make an authenticated API request with retry logic.

        This is the core request method that handles:
        - URL building
        - Authentication headers
        - Request UUID tracking
        - Retry logic with exponential backoff
        - Transient error handling

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/api-rm-reports/api/v1/rm-reports/position")
            return_body: If True, returns the parsed JSON response body instead of
                         {status_code, timestamp}. Use for synchronous endpoints
                         (e.g. get_account_information) that return data directly.
            **kwargs: Additional arguments for httpx request

        Returns:
            If return_body=False (default): Dict with status_code and timestamp.
            If return_body=True: parsed JSON body of the response.

        Raises:
            BTGRateLimitError: If rate limit is exceeded
            BTGAPIError: If API request fails
            TransientHTTPError: For retryable errors
        """
        await self._ensure_authenticated()

        # Build full URL
        if endpoint.startswith("/"):
            url = f"{self.base_url}{endpoint}"
        else:
            url = endpoint

        # Build headers
        headers = kwargs.pop("headers", {})
        headers.update({
            "accept": "*/*",
            "access_token": self._access_token,
            "x-id-partner-request": str(uuid.uuid4())
        })

        logger.debug(
            f"Making {method.upper()} request to {url} "
            f"with request ID: {headers['x-id-partner-request']}"
        )

        # Retry logic with exponential backoff
        async for attempt in AsyncRetrying(
                stop=stop_after_attempt(5),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                retry=retry_if_exception(_is_transient),
                reraise=True,
        ):
            with attempt:
                try:
                    response = await self._http_client.request(
                        method.upper(),
                        url,
                        headers=headers,
                        **kwargs
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    logger.warning(f"Transient error: {e}")
                    raise BTGTransientHTTPError(str(e)) from e

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning(f"Rate limit exceeded. Retry after {retry_after}s")
                    raise BTGRateLimitError(
                        f"Rate limit exceeded. Retry after {retry_after}s"
                    )

                # Retry on 5xx server errors
                if 500 <= response.status_code < 600:
                    logger.warning(f"Server error {response.status_code}, will retry")
                    raise BTGTransientHTTPError(f"Server error {response.status_code}")

                # Retry on 404 with a specific message (report not readying yet)
                if response.status_code == 404:
                    try:
                        body = response.json()
                        msg = str(body)
                    except Exception:
                        msg = response.text

                    if "Relatório não disponível" in msg:
                        logger.warning("Report not available yet (404), will retry")
                        raise BTGTransientHTTPError("Report not available yet (404)")

                # Check for other errors
                if response.status_code >= 400:
                    logger.error(
                        f"API error: {response.status_code} - {response.text}"
                    )
                    raise BTGAPIError(
                        f"API request failed: {response.status_code}"
                    )

                # Success
                if return_body:
                    return response.json()
                return {
                    "status_code": response.status_code,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }


    # ====================================================================
    # ADVISORS INFORMATION
    # ====================================================================

    async def get_office_informations_by_partner(self) -> Dict[str, Any]:
        """
        Get office information for the partner.

        Endpoint: GET /iaas-account-advisor/api/v1/advisor/office-informations

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching office information by partner")
        return await self._call_btg_api(
            "GET",
            "/iaas-account-advisor/api/v1/advisor/office-informations"
        )

    async def get_rm_reports_principality(self) -> Dict[str, Any]:
        """
        Get RM reports for principality.

        Endpoint: GET /api-rm-reports/api/v1/rm-reports/principality

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching RM reports principality")
        return await self._call_btg_api(
            "GET",
            "/api-rm-reports/api/v1/rm-reports/principality"
        )

    # ====================================================================
    # CUSTODY / POSITION
    # ====================================================================

    async def position_by_partner(self) -> Dict[str, Any]:
        """
        Refresh position by partner.

        Endpoint: GET /iaas-api-position/api/v1/position/refresh

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching position by partner (refresh)")
        return await self._call_btg_api(
            "GET",
            "/iaas-api-position/api/v1/position/refresh"
        )

    async def position_by_partner_v2(self) -> Dict[str, Any]:
        """
        Get position unit price history by partner (v2).

        Endpoint: GET /iaas-api-position/api/v2/position/unit-price/history/partner

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching position by partner v2 (unit-price/history)")
        return await self._call_btg_api(
            "GET",
            "/iaas-api-position/api/v2/position/unit-price/history/partner"
        )

    async def partner_report_custody(self) -> Dict[str, Any]:
        """
        Get partner custody report.

        Endpoint: GET /api-partner-report-extractor/api/v1/report/custody

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching partner report custody")
        return await self._call_btg_api(
            "GET",
            "/api-partner-report-extractor/api/v1/report/custody"
        )

    async def rm_reports_position(self) -> Dict[str, Any]:
        """
        Get RM reports position.

        Endpoint: GET /api-rm-reports/api/v1/rm-reports/position

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching RM reports position")
        return await self._call_btg_api(
            "GET",
            "/api-rm-reports/api/v1/rm-reports/position"
        )

    # ====================================================================
    # CLIENT REGISTRATION INFORMATION
    # ====================================================================

    async def rm_reports_registration_data(self) -> Dict[str, Any]:
        """
        Get RM reports registration data.

        Endpoint: GET /api-rm-reports/api/v1/rm-reports/registration-data

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching RM reports registration data")
        return await self._call_btg_api(
            "GET",
            "/api-rm-reports/api/v1/rm-reports/registration-data"
        )

    async def rm_reports_account_base(self) -> Dict[str, Any]:
        """
        Get RM reports account base.

        Endpoint: GET /api-rm-reports/api/v1/rm-reports/account-base

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching RM reports account base")
        return await self._call_btg_api(
            "GET",
            "/api-rm-reports/api/v1/rm-reports/account-base"
        )

    async def rm_reports_representative(self) -> Dict[str, Any]:
        """
        Get RM reports representative.

        Endpoint: GET /api-rm-reports/api/v1/rm-reports/representative

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching RM reports representative")
        return await self._call_btg_api(
            "GET",
            "/api-rm-reports/api/v1/rm-reports/representative"
        )

    async def rm_reports_banking(self) -> Dict[str, Any]:
        """
        Get RM reports banking.

        Endpoint: GET /api-rm-reports/api/v1/rm-reports/banking

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching RM reports banking")
        return await self._call_btg_api(
            "GET",
            "/api-rm-reports/api/v1/rm-reports/banking"
        )

    async def get_account_information(
            self,
            account_number: str
    ) -> Dict[str, Any]:
        """
        Get account information including holder, co-holders, and users.

        Endpoint: GET /iaas-account-management/api/v1/account-management/account/{account_number}/information

        This is a synchronous endpoint — the response body contains the full account
        JSON directly (no webhook callback). Example response:
        {
            "accountNumber": "000123456",
            "holder": {"name": "...", "taxIdentification": "..."},
            "coHolders": [{"name": "...", "taxIdentification": "..."}],
            "users": [
                {"name": "...", "userEmail": "...", "phoneNumber": "...", "isOwner": true}
            ]
        }

        Args:
            account_number: Account number (9 digits)
        Returns:
            Parsed JSON dict with account, holder, coHolders, and users fields.
        """
        logger.info(f"Fetching account information for {account_number}")
        return await self._call_btg_api(
            "GET",
            f"/iaas-account-management/api/v1/account-management/account/{account_number}/information",
            return_body=True,
        )


    # ====================================================================
    # OPEN FINANCE
    # ====================================================================

    async def rm_reports_openfinance(self) -> Dict[str, Any]:
        """
        Get RM reports open finance.

        Endpoint: GET /api-rm-reports/api/v1/rm-reports/openfinance

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching RM reports openfinance")
        return await self._call_btg_api(
            "GET",
            "/api-rm-reports/api/v1/rm-reports/openfinance"
        )

    async def rm_reports_consent_openfinance(self) -> Dict[str, Any]:
        """
        Get RM reports consent open finance.

        Endpoint: GET /api-rm-reports/api/v1/rm-reports/consent-openfinance

        Returns:
            Response with status_code and timestamp
        """
        logger.info("Fetching RM reports consent openfinance")
        return await self._call_btg_api(
            "GET",
            "/api-rm-reports/api/v1/rm-reports/consent-openfinance"
        )

    async def get_open_finance_position_by_account(
            self,
            account: str
    ) -> Dict[str, Any]:
        """
        Get open finance position for a specific account.

        Endpoint: GET /iaas-investment-consolidation/api/v1/open-finance/position/{account}

        Args:
            account: Account number

        Returns:
            Response with status_code and timestamp
        """
        logger.info(f"Fetching open finance position for account {account}")
        return await self._call_btg_api(
            "GET",
            f"/iaas-investment-consolidation/api/v1/open-finance/position/{account}"
        )

    # ====================================================================
    # UTILITY METHODS
    # ====================================================================

    async def health_check(self) -> bool:
        """
        Check if API is accessible and authentication works.

        Returns:
            True if healthy, False otherwise
        """
        try:
            await self._ensure_authenticated()
            logger.info("Health check passed")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False