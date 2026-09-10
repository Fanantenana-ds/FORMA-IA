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