# app/schemas/facture_ia.py
# ============================================================
# SCHÉMAS — ROUTES IA M7 (Facturation / relances)
# ============================================================

from typing import Optional

from pydantic import BaseModel, Field


class GenererRelanceRequest(BaseModel):
    """Corps de la requête pour générer une relance."""

    facture_id: str = Field(..., description="UUID Backend de la facture")


class CalculerMontantsRequest(BaseModel):
    """
    Corps de la requête pour calculer les montants d'une facture
    (Python pur, sans LLM) — voir FactureCalculatorService.calculer().
    """

    type_client: str = Field(..., description="'participant' ou 'entreprise'")
    nb_participants: int = Field(..., ge=1)
    tarif_unitaire: float = Field(..., gt=0)
    tva_taux: Optional[float] = Field(default=None, ge=0)
    remise_pct: Optional[float] = Field(
        default=None, ge=0, le=100,
        description="None = règle automatique (5% dès 15 participants)",
    )
    session_id: Optional[str] = Field(
        default=None, description="Référence Backend, recopiée dans la réponse"
    )
