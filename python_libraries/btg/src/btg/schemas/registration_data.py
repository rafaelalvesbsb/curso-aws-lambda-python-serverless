# src/btg/schemas/registration_data.py

"""
Schema for BTG Pactual Registration Data Report.

Validates the registration/cadastral data response from BTG API including:
- Personal details
- Contact information
- Document information
- Address
- Suitability and compliance
"""

from datetime import datetime, date
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class RegistrationData(BaseModel):
    """
    BTG Pactual Registration/Cadastral Data Report Schema.

    Validates complete registration information from BTG RM Reports API.
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True
    )

    # ========== ACCOUNT IDENTIFICATION ==========
    nr_conta: str = Field(..., description="Account number")
    tipo_cliente: Optional[str] = Field(None, description="Client type (PF/PJ)")
    status: Optional[str] = Field(
        None,
        description="Account status (ATIVA, BLOQUEIO PARCIAL, BLOQUEIO TOTAL, EM PROCESSO DE ENCERRAMENTO)"
    )

    # ========== PERSONAL INFORMATION ==========
    nome_completo: Optional[str] = Field(None, description="Full name")
    dt_nascimento: Optional[date] = Field(None, description="Birth date")
    profissao: Optional[str] = Field(None, description="Profession")
    estado_civil: Optional[str] = Field(None, description="Marital status")
    genero: Optional[str] = Field(None, description="Gender")
    idade: Optional[int] = Field(None, description="Age")
    nacionalidade: Optional[str] = Field(None, description="Nationality")
    residente: Optional[str] = Field(None, description="Resident (SIM/NÃO)")

    # ========== CONTACT INFORMATION ==========
    email_acesso: Optional[str] = Field(None, description="Access email (login)")
    telefone: Optional[str] = Field(None, description="Phone number")
    celular: Optional[str] = Field(None, description="Mobile phone")
    email_comunicacao: Optional[str] = Field(None, description="Communication email")

    # ========== DOCUMENT INFORMATION ==========
    documento_cpf_cnpj: Optional[str] = Field(None, description="CPF/CNPJ document number")
    documento_tipo: Optional[str] = Field(None, description="Document type (RG, CNH, etc)")
    documento: Optional[str] = Field(None, description="Document number")
    documento_dt_emissao: Optional[datetime] = Field(None, description="Document issue date")

    # ========== ADDRESS ==========
    endereco_cidade: Optional[str] = Field(None, description="City")
    endereco_completo: Optional[str] = Field(None, description="Full address")
    endereco_complemento: Optional[str] = Field(None, description="Address complement")
    endereco_estado: Optional[str] = Field(None, description="State (UF)")
    endereco_cep: Optional[str] = Field(None, description="ZIP code (CEP)")

    # ========== SUITABILITY & PROFILE ==========
    suitability: Optional[str] = Field(None, description="Suitability classification")
    dt_vencimento_suitability: Optional[date] = Field(None, description="Suitability expiration date")
    tipo_investidor: Optional[str] = Field(None, description="Investor type")
    perfil_acesso: Optional[str] = Field(None, description="Access profile")
    vencimento_cadastro: Optional[date] = Field(None, description="Registration expiration date")

    # ========== ACCOUNT LIFECYCLE DATES ==========
    dt_abertura: Optional[date] = Field(None, description="Account opening date")
    dt_encerramento: Optional[date] = Field(None, description="Account closing date")
    dt_primeiro_investimento: Optional[date] = Field(None, description="First investment date")
    dt_ult_revisao_cadastral: Optional[date] = Field(None, description="Last registration review date")
    dt_prox_revisao_castral: Optional[date] = Field(None, description="Next registration review date")
    dt_vinculo_escritorio: Optional[datetime] = Field(None, description="Office linkage date")

    # ========== FINANCIAL INFORMATION ==========
    vl_pl_declarado: Optional[float] = Field(None, description="Declared net worth (BRL)")
    vl_rendimento_total: Optional[float] = Field(None, description="Total income (BRL)")
    vl_rendimento_anual: Optional[float] = Field(None, description="Annual income (BRL)")

    # ========== OTHER FLAGS ==========
    cpf_conjuge: Optional[str] = Field(None, description="Spouse CPF")
    pendencia_cadastral: Optional[str] = Field(None, description="Registration pending flag")
