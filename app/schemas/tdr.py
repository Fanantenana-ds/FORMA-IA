# app/schemas/tdr.py
# ============================================================
# SCHÉMAS TDR — Pydantic (V4.0)
# ============================================================

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TDRRequest(BaseModel):
    """Brief client pour la génération de TDR."""
    client: str = Field(..., min_length=2)
    objectifs: str = Field(..., min_length=5)
    public: str = Field(..., min_length=2)
    duree: str = Field(..., min_length=1)
    format: Optional[str] = "Présentiel"
    budget: Optional[str] = None
    lieu: Optional[str] = None
    deadline: Optional[str] = None
    opportunite_id: Optional[str] = None       # ✅ Lien vers M1


class TDRFromOpportuniteRequest(BaseModel):
    """Requête pour pré-remplir depuis une opportunité."""
    opportunite_id: str


class TDRFromOpportuniteResponse(BaseModel):
    """Réponse avec le brief pré-rempli."""
    success: bool
    brief: Optional[Dict[str, Any]] = None
    opportunite: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TDRFiles(BaseModel):
    docx: Optional[str] = None
    pdf: Optional[str] = None


class TDRResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    files: Optional[TDRFiles] = None
    error: Optional[str] = None
    # Correction 1b : le TDR n'est plus envoyé au Backend directement à la
    # génération — un review HITL est créé, à approuver puis synchroniser
    # via POST /ia/tdr/synchroniser (même mécanisme que M3).
    review_id: Optional[str] = None
    review_status: Optional[str] = None


class SynchroniserTDRRequest(BaseModel):
    """Corps de la requête pour enregistrer un TDR APPROUVÉ dans le Backend."""
    review_id: str = Field(
        ..., description="ID du review APPROUVÉ du TDR (agent_m2_tdr)"
    )
    opportunite_id: Optional[str] = Field(
        default=None,
        description="UUID de l'opportunité Backend liée (sinon lu dans le brief mémorisé)",
    )
    force: bool = Field(
        default=False,
        description="Renvoyer même si déjà synchronisé (crée un nouveau document Backend)",
    )