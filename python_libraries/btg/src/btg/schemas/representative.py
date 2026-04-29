# src/btg/schemas/representative.py

"""
Schema for BTG Pactual Account Representative.

Validates the representative data response from BTG API including:
- Representative identification
- Contact details
- Access profile and permissions
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class Representative(BaseModel):
    """
    BTG Pactual Account Representative Schema.

    Validates information about account representatives (procuradores).
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True
    )

    # ========== ACCOUNT LINK ==========
    nr_conta: str = Field(..., description="Account number represented")

    # ========== REPRESENTATIVE INFO ==========
    nome_representante: str = Field(..., description="Representative full name")
    cpf_representante: Optional[str] = Field(None, description="Representative CPF")
    celular: Optional[str] = Field(None, description="Mobile phone")
    email: str = Field(..., description="Email address")
    idade: Optional[int] = Field(None, description="Age")
    dt_nascimento: Optional[date] = Field(None, description="Birth date")

    # ========== ACCESS & PERMISSIONS ==========
    perfil: Optional[str] = Field(None, description="Access profile")
    tipo_representante: Optional[str] = Field(None, description="Representative type (COMUM/MASTER)")
    flag_menor: Optional[str] = Field(None, description="Minor flag (SIM/NÃO)")
