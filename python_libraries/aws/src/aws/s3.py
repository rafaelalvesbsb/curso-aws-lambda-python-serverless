# src/aws/s3.py

"""
S3 Client for AWS Data Lake operations.

This module provides a synchronous S3 client for interacting with AWS S3,
specifically designed for the AGFI Data Lake with partitioned data structure.

Typical usage example:
    from src.aws.s3 import S3Client

    client = S3Client(
        bucket_name="agfi-data-lake-dev",
        region="us-east-2"
    )

    # Read latest partition
    df = client.read_last_partition_csv(
        source="rm-reports-account-base",
        event_date="20250115"
    )
"""

import io
from pathlib import Path
from typing import Optional, Dict, Any

import boto3
import pandas as pd
from botocore.config import Config
from loguru import logger


def _extract_partition_info(file_name: str) -> Optional[Dict[str, str]]:
    """
    Extract metadata from a partitioned file name.

    Parses file names with the format:
    {base_name}--{key1}={value1}--{key2}={value2}.{extension}

    Args:
        file_name: Full file path or name
                  Example: "rm-reports-account-base--eventts=20251001T143806Z--hash=abc123.csv"

    Returns:
        Dictionary with extracted metadata or None if parsing fails
        Example: {"eventts": "20251001T143806Z", "hash": "abc123"}
    """
    try:
        base_name = Path(file_name).stem  # Remove directory and extension
        parts = base_name.split('--')

        info_dict = {}
        for part in parts[1:]:  # Skip the first part (base name)
            if '=' in part:
                key, value = part.split('=', 1)
                info_dict[key] = value

        return info_dict if info_dict else None

    except Exception as e:
        logger.error(f"Failed to parse partition file name: {file_name}", error=str(e))
        return None


class S3Client:
    """
    Synchronous S3 Client for AWS Data Lake operations.

    This client handles interactions with S3, including reading partitioned data,
    listing files, and identifying the latest data partitions.

    Attributes:
        bucket_name: S3 bucket name
        region: AWS region
        client: boto3 S3 client instance
        log: Loguru logger with context binding
    """

    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-2",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        """
        Initialize S3 Client.

        Args:
            bucket_name: Name of the S3 bucket
            region: AWS region (default: us-east-2)
            aws_access_key_id: AWS access key (optional, uses boto3 default chain if not provided)
            aws_secret_access_key: AWS secret key (optional, uses boto3 default chain if not provided)

        Note:
            If credentials are not provided, boto3 will use the default credential chain:
            1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
            2. AWS credentials file (~/.aws/credentials)
            3. IAM role (when running on EC2/Lambda)
        """
        self.bucket_name = bucket_name
        self.region = region

        # Configure boto3 client
        config = Config(
            region_name=region,
            s3={"addressing_style": "path"}
        )

        # Build client kwargs
        client_kwargs: Dict[str, Any] = {"config": config}

        # Only add credentials if explicitly provided
        if aws_access_key_id and aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = aws_access_key_id
            client_kwargs["aws_secret_access_key"] = aws_secret_access_key

        self.client = boto3.client('s3', **client_kwargs)
        self.log = logger.bind(service="s3_client", bucket=bucket_name)

        self.log.info("S3 client initialized", region=region)


    def read_last_partition_csv(
        self,
        source: str,
        event_date: str,
        domain: str = "btg",
        separator: str = ";"
    ) -> pd.DataFrame:
        """
        Read the most recent partitioned CSV file from S3.

        This method lists all files in a partition, identifies the latest one
        based on the eventts timestamp, and reads it into a DataFrame.

        Args:
            source: Data source identifier (e.g., "rm-reports-account-base")
            event_date: Partition date in YYYYMMDD format (e.g., "20250115")
            domain: Domain/namespace for data organization (default: "btg")
            separator: CSV separator character (default: ";")

        Returns:
            Pandas DataFrame with the CSV data, or empty DataFrame if no file found

        Example:
            >>> client = S3Client(bucket_name="agfi-data-lake-dev")
            >>> df = client.read_last_partition_csv(
            ...     source="rm-reports-account-base",
            ...     event_date="20250115"
            ... )
        """
        partition_path = f"raw/domain={domain}/source={source}/event_date={event_date}/"

        self.log.info("Reading CSV from partition", partition=partition_path)

        # List all files in partition
        partition_files = self.list_partition_files(
            source=source,
            event_date=event_date,
            domain=domain
        )

        # Identify the latest file
        latest_file = self.identify_last_partition(partition_files)

        if not latest_file:
            self.log.warning("No valid partition file found")
            return pd.DataFrame()

        # Read file from S3
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=latest_file
            )

            # Read CSV into DataFrame
            df = pd.read_csv(
                io.BytesIO(response['Body'].read()),
                sep=separator
            )

            self.log.info(
                "Successfully read CSV",
                file=latest_file,
                records=len(df),
                columns=len(df.columns)
            )

            return df

        except Exception as e:
            self.log.error("Failed to read CSV from S3", file=latest_file, error=str(e))
            return pd.DataFrame()


    def list_partition_files(
        self,
        source: str,
        event_date: str,
        domain: str = "btg",
        extension: str = ".csv"
    ) -> list[str]:
        """
        List all files in a specific S3 partition.

        Args:
            source: Data source identifier
            event_date: Partition date in YYYYMMDD format
            domain: Domain/namespace for data organization
            extension: File extension to filter (default: ".csv")

        Returns:
            List of S3 object keys (file paths)

        Example:
            >>> client = S3Client(bucket_name="agfi-data-lake-dev")
            >>> files = client.list_partition_files(
            ...     source="rm-reports-account-base",
            ...     event_date="20250115"
            ... )
            >>> print(files)
            ['raw/.../rm-reports--eventts=20250115T120000Z--hash=abc.csv']
        """
        partition_path = f"raw/domain={domain}/source={source}/event_date={event_date}/"

        self.log.debug("Listing partition files", partition=partition_path)

        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=partition_path
            )

            if 'Contents' not in response:
                self.log.warning("No files found in partition", partition=partition_path)
                return []

            # Filter files by extension
            files = [
                obj['Key']
                for obj in response['Contents']
                if obj['Key'].endswith(extension)
            ]

            self.log.info(
                "Found files in partition",
                partition=partition_path,
                count=len(files)
            )

            return files

        except Exception as e:
            self.log.error("Failed to list partition files", partition=partition_path, error=str(e))
            return []


    def identify_last_partition(
        self,
        partition_files: list[str],
    ) -> Optional[str]:
        """
        Identify the most recent partition file based on eventts timestamp.

        Parses file names to extract the 'eventts' field and returns the file
        with the latest timestamp.

        Args:
            partition_files: List of S3 object keys (file paths)

        Returns:
            S3 key of the latest file, or None if no valid files found

        Example:
            >>> files = [
            ...     "path/file--eventts=20250115T100000Z--hash=abc.csv",
            ...     "path/file--eventts=20250115T120000Z--hash=def.csv",
            ... ]
            >>> latest = client.identify_last_partition(files)
            >>> print(latest)
            'path/file--eventts=20250115T120000Z--hash=def.csv'
        """
        if not partition_files:
            self.log.warning("No partition files provided")
            return None

        files_by_timestamp = {}

        for file_path in partition_files:
            info = _extract_partition_info(file_path)

            if info and 'eventts' in info:
                files_by_timestamp[info['eventts']] = file_path

        if not files_by_timestamp:
            self.log.warning("No valid partition files with eventts found")
            return None

        # Get file with latest timestamp
        latest_timestamp = max(files_by_timestamp.keys())
        latest_file = files_by_timestamp[latest_timestamp]

        self.log.info(
            "Identified latest partition",
            file=latest_file,
            eventts=latest_timestamp
        )

        return latest_file


    def upload_file(
        self,
        file_path: str,
        s3_key: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Upload a local file to S3.

        Args:
            file_path: Local file path to upload
            s3_key: Destination S3 object key (path in bucket)
            metadata: Optional metadata to attach to the S3 object

        Returns:
            True if upload succeeded, False otherwise
        """
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata

            self.client.upload_file(
                Filename=file_path,
                Bucket=self.bucket_name,
                Key=s3_key,
                ExtraArgs=extra_args if extra_args else None
            )

            self.log.info("File uploaded successfully", s3_key=s3_key)
            return True

        except Exception as e:
            self.log.error("Failed to upload file", s3_key=s3_key, error=str(e))
            return False


    def upload_dataframe_as_csv(
        self,
        df: pd.DataFrame,
        s3_key: str,
        separator: str = ";",
        index: bool = False
    ) -> bool:
        """
        Upload a Pandas DataFrame as CSV to S3.

        Args:
            df: Pandas DataFrame to upload
            s3_key: Destination S3 object key
            separator: CSV separator (default: ";")
            index: Whether to include DataFrame index (default: False)

        Returns:
            True if upload succeeded, False otherwise
        """
        try:
            # Convert DataFrame to CSV in memory
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, sep=separator, index=index)

            # Upload to S3
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=csv_buffer.getvalue().encode('utf-8')
            )

            self.log.info(
                "DataFrame uploaded as CSV",
                s3_key=s3_key,
                records=len(df),
                columns=len(df.columns)
            )
            return True

        except Exception as e:
            self.log.error("Failed to upload DataFrame", s3_key=s3_key, error=str(e))
            return False
