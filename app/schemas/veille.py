# app/schemas/veille.py
# ============================================================
# SCHÉMA PARTAGÉ IA <-> BACKEND — MODULE M1 VEILLE MARCHÉ
# ============================================================
# Zone SHARED (cf. répartition des rôles) : ce schéma est le
# contrat d'interface entre ton module IA et le module Backend
# de ton binôme.
#
# Ton IA ne connaît pas PostgreSQL.
# Le Backend ne connaît pas Groq/Tavily.
# Ce schéma est la frontière entre les deux.
# ============================================================

from typing import List, Optional

from pydantic import BaseModel, Field


class OpportunityResult(BaseModel):
    """
    Une opportunité détectée par M1, prête à être consommée
    par le Backend (POST /api/v1/opportunities) ou le Frontend.
    """

    title: str
    source: Optional[str] = None
    source_site: Optional[str] = None
    source_priority: Optional[str] = None
    url: str
    budget: Optional[str] = "Non précisé"
    deadline: Optional[str] = None
    organizer: Optional[str] = None
    domain: Optional[str] = "autre"
    opportunity_type: Optional[str] = "autre"
    summary: Optional[str] = None
    is_actionable: bool = False
    score: int = Field(default=0, ge=0, le=100)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: Optional[str] = "to_review"
    country_scope: Optional[str] = None
    ai_provider: Optional[str] = None
    reason: Optional[str] = None
    flags: List[str] = Field(default_factory=list)


class VeilleResponse(BaseModel):
    """Réponse complète du endpoint POST /api/v1/ia/veille/rechercher"""

    query: str
    total_results: int
    opportunities: List[OpportunityResult]
    status: str
    notes: Optional[str] = None