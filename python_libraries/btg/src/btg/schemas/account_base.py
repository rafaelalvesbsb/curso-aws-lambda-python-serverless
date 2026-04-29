# src/btg/schemas/account_base.py

"""
Schema for BTG Pactual Account Base Report.

Validates the account base report response from BTG API including:
- Client identification
- Portfolio composition (PL by asset class)
- Investment activity (deposits, withdrawals)
- Advisor/Partner information
"""

from datetime import datetime, date
from typing import Optional, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class AccountBase(BaseModel):
    """
    BTG Pactual Account Base Report Schema.

    Validates account information from BTG RM Reports API.
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True
    )

    # ========== IDENTIFICATION ==========
    nr_conta: str = Field(..., description="Account number")
    id_cliente: Optional[str] = Field(None, description="Client hash ID (BTG internal)")

    # ========== CLIENT INFO ==========
    nome_completo: str = Field(..., description="Full client name")
    email: Optional[str] = Field(None, description="Client email")
    tipo_cliente: Optional[str] = Field(None, description="Client type (PF/PJ)")
    dt_nascimento: Optional[date] = Field(None, description="Birth date")
    profissao: Optional[str] = Field(None, description="Profession")
    estado_civil: Optional[str] = Field(None, description="Marital status")

    # ========== ADDRESS ==========
    endereco_cidade: Optional[str] = Field(None, description="City")
    endereco_estado: Optional[str] = Field(None, description="State (UF)")

    # ========== ACCOUNT DATES ==========
    dt_abertura: Optional[date] = Field(None, description="Account opening date")
    dt_vinculo: Optional[datetime] = Field(None, description="Client linkage date")
    dt_vinculo_escritorio: Optional[datetime] = Field(None, description="Office linkage date")
    dt_primeiro_investimento: Optional[date] = Field(None, description="First investment date")
    dt_ultimo_aporte: Optional[date] = Field(None, description="Last deposit date")

    # ========== INVESTOR PROFILE ==========
    perfil_investidor: Optional[str] = Field(None, description="Investor profile/risk tolerance")
    termo_curva_rf: Optional[str] = Field(None, description="Fixed income curve term")
    faixa_cliente: Optional[str] = Field(None, description="Client tier/segment")

    # ========== ACTIVITY METRICS ==========
    qtd_aportes: Optional[int] = Field(None, description="Number of deposits")
    vl_aportes: Optional[float] = Field(None, description="Total deposits (BRL)")
    vl_retiradas: Optional[float] = Field(None, description="Total withdrawals (BRL)")

    # ========== POSITION COUNTS BY ASSET CLASS ==========
    qtd_ativos: Optional[int] = Field(None, description="Total number of assets")
    qtd_fundos: Optional[int] = Field(None, description="Number of funds")
    qtd_renda_fixa: Optional[int] = Field(None, description="Number of fixed income positions")
    qtd_renda_variavel: Optional[int] = Field(None, description="Number of variable income positions")
    qtd_previdencia: Optional[int] = Field(None, description="Number of pension positions")
    qtd_derivativos: Optional[int] = Field(None, description="Number of derivatives")
    qtd_valores_transito: Optional[float] = Field(None, description="Values in transit")

    # ========== PORTFOLIO VALUE (PL) BY ASSET CLASS ==========
    pl_total: Optional[float] = Field(None, description="Total portfolio value (BRL)")
    pl_conta_corrente: Optional[float] = Field(None, description="Cash balance (BRL)")
    pl_fundos: Optional[float] = Field(None, description="Funds portfolio value (BRL)")
    pl_renda_fixa: Optional[float] = Field(None, description="Fixed income portfolio value (BRL)")
    pl_renda_variavel: Optional[float] = Field(None, description="Variable income portfolio value (BRL)")
    pl_previdencia: Optional[float] = Field(None, description="Pension portfolio value (BRL)")
    pl_derivativos: Optional[float] = Field(None, description="Derivatives portfolio value (BRL)")
    pl_valores_transito: Optional[float] = Field(None, description="Values in transit (BRL)")

    # ========== FINANCIAL DECLARATIONS ==========
    vl_pl_declarado: Optional[float] = Field(None, description="Declared net worth (BRL)")
    vl_rendimento_anual: Optional[float] = Field(None, description="Annual income (BRL)")

    # ========== PARTNER (SÓCIO) INFO ==========
    cge_partner: Optional[int] = Field(None, description="Partner CGE code")
    nm_partner: Optional[str] = Field(None, description="Partner name")

    # ========== ADVISOR (ASSESSOR) INFO ==========
    cge_officer: Optional[int] = Field(None, description="Advisor CGE code")
    nm_officer: Optional[str] = Field(None, description="Advisor name")
    email_assessor: Optional[str] = Field(None, description="Advisor email")
    tipo_parceiro: Optional[str] = Field(None, description="Partner type")

    # ========== MANAGED PORTFOLIO ==========
    carteira_administrada: Optional[Any] = Field(None, description="Managed portfolio flag")
