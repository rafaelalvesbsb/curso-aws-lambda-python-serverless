# /src/core/config.py

"""
Centralized configuration management for AGFI Data Pipeline.

This module uses Pydantic Settings to load and validate configuration from:
- Environment Variables
- .env files
- Default values

Usage:
    from src.core.config import settings

    # Access configuration
    s3_client = S3Client(bucket_name=settings.S3_BUCKET)
    btg_client = BTGClient(
        client_id=settings.BTG_CLIENT_ID,
        client_secret=settings.BTG_CLIENT_SECRET,)
"""

from pathlib import Path
from typing import Optional, Literal
from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env files.

    All settings are validated at startup to catch configuration errors early.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore", # Ignore unknown environment variables
    )

    # =========================================================
    # ENVIRONMENT
    # =========================================================
    ENVIRONMENT: Literal["dev", "staging", "prod"] = Field(
        default="dev",
        description="Application environment",
    )

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="DEBUG",
        description="Logging level",
    )

    # =========================================================
    # AWS - GENERAL
    # =========================================================
    AWS_REGION: str = Field(
        default="us-east-2",
        description="AWS region for all services",
    )

    AWS_ACCESS_KEY_ID: Optional[str] = Field(
        default=None,
        description="AWS Access Key(optional, uses IAM role if not provided)",
    )

    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(
        default=None,
        description="AWS Secret Key(optional, uses IAM role if not provided)",
    )

    # =========================================================
    # AWS - S3
    # =========================================================
    S3_BUCKET: str = Field(
        default="agfi",
        description="S3 bucket name for data storage",
    )

    # =========================================================
    # AWS - DYNAMODB
    # =========================================================
    DYNAMODB_SYNC_STATE_TABLE: Optional[str] = Field(
        default=None,
        description="DynamoDB table for sync state tracking",
    )

    # =========================================================
    # AWS - SQS
    # =========================================================
    SQS_QUEUE_URL: Optional[str] = Field(
        default=None,
        description="SQS queue URL for async processing",
    )

    # =========================================================
    # AWS - SNS
    # ========================================================
    SNS_NOTIFICATION_TOPIC: Optional[str] = Field(
        default=None,
        description="SNS topic ARN for notifications",
    )
    # =========================================================
    # BTG PACTUAL API
    # =========================================================
    BTG_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="BTG Pactual API Client ID",
    )

    BTG_CLIENT_SECRET: Optional[str] = Field(
        default=None,
        description="BTG Pactual API Client Secret",
    )

    BTG_BASE_URL: str = Field(
        default="https://api.btgpactual.com",
        description="Base URL for BTG Pactual API",
    )

    TOKEN_EXPIRATION_BUFFER_SECONDS: int = Field(
        default=300,
        ge=0,
        le=3600,
        description="Token refresh buffer time in seconds (before actual expiration)",
    )

    # =========================================================
    # HUBSPOT CRM
    # =========================================================
    HUBSPOT_API_KEY: Optional[str] = Field(
        default=None,
        description="HubSpot API Key (Private App Token)",
    )

    HUBSPOT_PORTAL_ID: Optional[str] = Field(
        default=None,
        description="HubSpot Portal ID",
    )

    HUBSPOT_CUSTOM_OBJECT_TYPE_ID_ACCOUNT: str = Field(
        default="2-51787688",
        description="HubSpot Custom Object Type ID for Account (Conta)",
    )

    # =========================================================
    # MYSQL DATABASE (Optional)
    # =========================================================
    MYSQL_HOST: Optional[str] = Field(
        default=None,
        description="MySQL database host",
    )

    MYSQL_PORT: Optional[int] = Field(
        default=3306,
        ge=1,
        le=65535,
        description="MySQL database port",
    )
    MYSQL_DATABASE: Optional[str] = Field(
        default=None,
        description="MySQL database name",
    )

    MYSQL_USER: Optional[str] = Field(
        default=None,
        description="MySQL database user",
    )

    MYSQL_PASSWORD: Optional[str] = Field(
        default=None,
        description="MySQL database password",
    )

    # =========================================================
    # REDIS (Optional)
    # =========================================================
    REDIS_HOST: Optional[str] = Field(
        default="localhost",
        description="Redis server host",
    )

    REDIS_PORT: Optional[int] = Field(
        default=6379,
        ge=1,
        le=65535,
        description="Redis server port",
    )

    # =========================================================
    # HTTP CLIENT SETTINGS
    # =========================================================
    HTTP_TIMEOUT: int = Field(
        default=30,
        ge=1,
        le=300,
        description="HTTP client timeout in seconds",
    )

    REQUEST_TIMEOUT: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Request timeout for BTG API calls in seconds",
    )

    MAX_RETRIES: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts"
    )

    RETRY_BACKOFF_MULTIPLIER: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Backoff multiplier for exponential retry"
    )

    # =========================================================
    # HEALTHCHECK (Optional)
    # =========================================================
    HC_PING_URL: Optional[str] = Field(
        default=None,
        description="Healthcheck ping URL (e.g., healthchecks.io)"
    )

    HC_PING_INTERVAL_SECONDS: int = Field(
        default=600,
        ge=60,
        le=3600,
        description="Healthcheck ping interval in seconds"
    )

    HC_PING_TIMEOUT_SECONDS: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Healthcheck ping timeout in seconds"
    )

    # =========================================================
    # PATHS
    # =========================================================
    DATA_DIR: Path = Field(
        default=Path("data"),
        description="Base directory for data files",
    )

    BACKUP_DIR: Path = Field(
        default=Path("data/backups"),
        description="Directory for backups",
    )

    # =========================================================
    # VALIDATORS
    # =========================================================
    @field_validator("S3_BUCKET")
    @classmethod
    def validate_s3_bucket(cls, v: str) -> str:
        """
        S3 bucket names must be lowercase.
        :param v:
        :return: str
        """
        return v.strip()

    # ========================================================
    # COMPUTED PROPERTIES
    # ========================================================
    @computed_field
    @property
    def is_dev(self) -> bool:
        """
        Check if running in development environment.
        :return:
        """
        return self.ENVIRONMENT == "dev"

    @computed_field
    @property
    def is_prod(self) -> bool:
        """
        Check if running in production environment.
        :return:
        """
        return self.ENVIRONMENT == "prod"

    @computed_field
    @property
    def s3_bucket_name(self) -> str:
        """
        Get the full S3 bucket name with environment suffix.
        :return:
        """
        return f"{self.S3_BUCKET}-{self.ENVIRONMENT}"

    @computed_field
    @property
    def dynamodb_table_name(self) -> Optional[str]:
        """
        Get the DynamoDB table name with environment suffix.
        :return:
        """
        if not self.DYNAMODB_SYNC_STATE_TABLE:
            return None
        return f"{self.DYNAMODB_SYNC_STATE_TABLE}-{self.ENVIRONMENT}"

    @computed_field
    @property
    def has_mysql_config(self) -> bool:
        """
        Check if MySQL is configured.
        :return: bool
        """
        return all([
            self.MYSQL_HOST,
            self.MYSQL_DATABASE,
            self.MYSQL_USER,
            self.MYSQL_PASSWORD,
        ])

    # =======================================================
    # HELPER METHODS
    # =======================================================
    def get_s3_partition_path(
        self,
        layer: Literal["raw", "bronze", "silver", "gold"],
        domain: str,
        source: str,
        event_date: str,
    ) -> str:
        """
        Generate S3 partition path following data lake structure.

        Args:
            layer: Data lake layer (raw, bronze, silver, gold)
            domain: Domain/namespace (e.g., "btg")
            source: Data source (e.g., "rm-reports-account-base")
            event_date: Event date in YYYYMMDD format

        Returns:
            S3 path: "{layer}/domain={domain}/source={source}/event_date={event_date}/"
        """
        return f"{layer}/domain={domain}/source={source}/event_date={event_date}/"

    def __repr__(self) -> str:
        """
        Safe repr tha doesn't expose secrets.
        """
        safe_fields =[
            "ENVIRONMENT",
            "LOG_LEVEL",
            "AWS_REGION",
            "S3_BUCKET",
            "BTG_BASE_URL",
        ]

        safe_values = {k: getattr(self, k) for k in safe_fields}
        return f"Settings({safe_values})"

# ========================================================
# GLOBAL SETTINGS INSTANCE
# ========================================================
settings = Settings()

# =======================================================
# EXPORT
# =======================================================
__all__ = ["settings", "Settings"]