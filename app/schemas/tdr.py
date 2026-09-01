# ============================================================
# SCHEMAS M2 — TDR (CONTRAT IA ↔ BACKEND)
# ============================================================

from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class TDRRequest(BaseModel):
    """Requête pour la génération d'un TDR"""
    client: str
    objectifs: str
    public: str
    duree: str
    format: Optional[str] = "Présentiel"
    budget: Optional[str] = None


class TDRSection(BaseModel):
    """Section d'un TDR"""
    titre: str
    contenu: str


class TDRData(BaseModel):
    """Données d'un TDR"""
    titre: str
    sections: Dict[str, str]
    date_generation: Optional[str] = None


class TDRResponse(BaseModel):
    """Réponse pour la génération d'un TDR"""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None


class TDRDocument(BaseModel):
    """Document TDR généré"""
    id: Optional[int] = None
    client: str
    titre: str
    contenu: str
    format: str
    url: Optional[str] = None
    created_at: Optional[str] = None