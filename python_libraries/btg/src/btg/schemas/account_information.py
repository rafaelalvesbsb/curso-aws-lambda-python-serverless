# src/btg/schemas/account_information.py

"""
Schemas for BTG Pactual Account Information API.

This module provides TWO schemas for different processing stages:

1. AccountInformationRaw: Validates the raw nested JSON from BTG API
2. AccountInformationFlat: Validates the flattened DataFrame after json_normalize()

API endpoint: /api/v1/account-management/account/{accountNumber}/information
Reference: docs/sources/btg/api/API de Dados Cadastrais.yaml

Processing flow:
  BTG API → AccountInformationRaw (validate) → _flat_users_key() →
  pd.json_normalize() → rename columns → AccountInformationFlat (validate)
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# RAW SCHEMAS - Validate nested JSON from BTG API
# ============================================================================

class Holder(BaseModel):
    """Account holder (titular) information."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True
    )

    name: str = Field(..., description="Holder name")
    taxIdentification: str = Field(..., alias="taxIdentification", description="CPF/CNPJ of the holder")


class CoHolder(BaseModel):
    """Account co-holder (cotitular) information."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True
    )

    name: str = Field(..., description="Co-holder name")
    taxIdentification: str = Field(..., alias="taxIdentification", description="CPF/CNPJ of the co-holder")


class User(BaseModel):
    """Account user information."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True
    )

    name: str = Field(..., description="User name")
    userEmail: str = Field(..., alias="userEmail", description="User email")
    phoneNumber: Optional[str] = Field(None, alias="phoneNumber", description="User phone number")
    isOwner: bool = Field(..., alias="isOwner", description="Flag indicating if user is the account owner")


class AccountInformationRaw(BaseModel):
    """
    Raw BTG Pactual Account Information from API.

    Validates the NESTED JSON structure returned by BTG API.
    Use this schema BEFORE flattening the data.

    Example JSON from API:
    {
        "accountNumber": "000123456",
        "holder": {
            "name": "José Antônio",
            "taxIdentification": "12345678900"
        },
        "coHolders": [
            {
                "name": "Maria Helena",
                "taxIdentification": "98765432100"
            }
        ],
        "users": [
            {
                "name": "José Antônio",
                "userEmail": "jose@email.com",
                "phoneNumber": "11-99999",
                "isOwner": true
            }
        ]
    }
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True
    )

    # ========== ACCOUNT IDENTIFICATION ==========
    accountNumber: str = Field(..., alias="accountNumber", description="Account number")

    # ========== HOLDER (TITULAR) ==========
    holder: Holder = Field(..., description="Account holder information")

    # ========== CO-HOLDERS (COTITULARES) ==========
    coHolders: Optional[list[CoHolder]] = Field(
        default=None,
        alias="coHolders",
        description="List of account co-holders"
    )

    # ========== USERS ==========
    users: Optional[list[User]] = Field(
        default=None,
        description="List of account users"
    )


# ============================================================================
# FLAT SCHEMAS - Validate flattened DataFrame after json_normalize()
# ============================================================================

class AccountInformationFlat(BaseModel):
    """
    Flattened BTG Account Information after json_normalize().

    This schema validates data AFTER:
    1. _flat_users_key() flattens users array → user_0_name, user_1_name, etc
    2. pd.json_normalize() flattens nested objects → holder.name, coHolder.name
    3. Column renaming with BTG_ACCOUNT_API_TO_STANDARD mapping

    Expected DataFrame columns after processing:
    - account_number (from accountNumber)
    - holder_name (from holder.name)
    - holder_tax_id (from holder.taxIdentification)
    - primary_user_name (from user_0_name)
    - primary_user_email (from user_0_userEmail)
    - primary_user_phone (from user_0_phoneNumber)
    - primary_user_is_owner (from user_0_isOwner)
    - secondary_user_name (from user_1_name)
    - secondary_user_email (from user_1_userEmail)
    - secondary_user_phone (from user_1_phoneNumber)
    - secondary_user_is_owner (from user_1_isOwner)
    - tertiary_user_name (from user_2_name)
    - tertiary_user_email (from user_2_userEmail)
    - tertiary_user_phone (from user_2_phoneNumber)
    - tertiary_user_is_owner (from user_2_isOwner)
    - fourth_user_name (from user_3_name, if exists)
    - fourth_user_email (from user_3_userEmail, if exists)
    - fourth_user_phone (from user_3_phoneNumber, if exists)
    - fourth_user_is_owner (from user_3_isOwner, if exists)
    - co_holder_name (from coHolder.name - first coHolder only)
    - co_holder_tax_id (from coHolder.taxIdentification - first coHolder only)

    This matches the structure saved in:
    - database_tmp/accounts_users_info.parquet (via upsert_account_users_info_parquet)
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True
    )

    # ========== ACCOUNT IDENTIFICATION ==========
    account_number: str = Field(..., description="Account number (9 digits zero-padded)")

    # ========== HOLDER (TITULAR) ==========
    holder_name: str = Field(..., description="Holder full name")
    holder_tax_id: str = Field(..., description="Holder CPF/CNPJ")

    # ========== PRIMARY USER (user_0) - OPTIONAL ==========
    primary_user_name: Optional[str] = Field(None, description="Primary user name")
    primary_user_email: Optional[str] = Field(None, description="Primary user email")
    primary_user_phone: Optional[str] = Field(None, description="Primary user phone")
    primary_user_is_owner: Optional[bool] = Field(None, description="Is primary user the owner")

    # ========== SECONDARY USER (user_1) - OPTIONAL ==========
    secondary_user_name: Optional[str] = Field(None, description="Secondary user name")
    secondary_user_email: Optional[str] = Field(None, description="Secondary user email")
    secondary_user_phone: Optional[str] = Field(None, description="Secondary user phone")
    secondary_user_is_owner: Optional[bool] = Field(None, description="Is secondary user the owner")

    # ========== TERTIARY USER (user_2) - OPTIONAL ==========
    tertiary_user_name: Optional[str] = Field(None, description="Tertiary user name")
    tertiary_user_email: Optional[str] = Field(None, description="Tertiary user email")
    tertiary_user_phone: Optional[str] = Field(None, description="Tertiary user phone")
    tertiary_user_is_owner: Optional[bool] = Field(None, description="Is tertiary user the owner")

    # ========== FOURTH USER (user_3) - OPTIONAL ==========
    fourth_user_name: Optional[str] = Field(None, description="Fourth user name")
    fourth_user_email: Optional[str] = Field(None, description="Fourth user email")
    fourth_user_phone: Optional[str] = Field(None, description="Fourth user phone")
    fourth_user_is_owner: Optional[bool] = Field(None, description="Is fourth user the owner")

    # ========== CO-HOLDER (only first one) - OPTIONAL ==========
    co_holder_name: Optional[str] = Field(None, description="Co-holder name (first only)")
    co_holder_tax_id: Optional[str] = Field(None, description="Co-holder CPF/CNPJ (first only)")
