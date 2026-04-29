# src/btg/schemas/__init__.py

"""
Pydantic schemas for BTG Pactual API responses.

These schemas validate data coming from BTG API endpoints.
"""

from .account_base import AccountBase
from .registration_data import RegistrationData
from .representative import Representative
from .account_information import (
    AccountInformationRaw,
    AccountInformationFlat,
    Holder,
    CoHolder,
    User
)

__all__ = [
    "AccountBase",
    "RegistrationData",
    "Representative",
    # Account Management API schemas - RAW (nested JSON)
    "AccountInformationRaw",
    "Holder",
    "CoHolder",
    "User",

    # Account Management API schemas - FLAT (after json_normalize)
    "AccountInformationFlat",
]
