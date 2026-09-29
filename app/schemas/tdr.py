# app/schemas/tdr.py
# ============================================================
# SCHÉMAS TDR — Pydantic (V4.0)
# ============================================================

from typing import Any

from pydantic import BaseModel, Field


class TDRRequest(BaseModel):
    """Brief client pour la génération de TDR."""
    client: str = Field(..., min_length=2)
    objectifs: str = Field(..., min_length=5)
    public: str = Field(..., min_length=2)
    duree: str = Field(..., min_length=1)
    format: str | None = "Présentiel"
    budget: str | None = None
    lieu: str | None = None
    deadline: str | None = None
    opportunite_id: str | None = None       # ✅ Lien vers M1


class TDRFromOpportuniteRequest(BaseModel):
    """Requête pour pré-remplir depuis une opportunité."""
    opportunite_id: str


class TDRFromOpportuniteResponse(BaseModel):
    """Réponse avec le brief pré-rempli."""
    success: bool
    brief: dict[str, Any] | None = None
    opportunite: dict[str, Any] | None = None
    error: str | None = None


class TDRFiles(BaseModel):
    docx: str | None = None
    pdf: str | None = None


class TDRResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    files: TDRFiles | None = None
    error: str | None = None