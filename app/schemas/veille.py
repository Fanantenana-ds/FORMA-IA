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


from pydantic import BaseModel, Field


class OpportunityResult(BaseModel):
    """
    Une opportunité détectée par M1, prête à être consommée
    par le Backend (POST /api/v1/opportunities) ou le Frontend.
    """

    title: str
    source: str | None = None
    source_site: str | None = None
    source_priority: str | None = None
    url: str
    budget: str | None = "Non précisé"
    deadline: str | None = None
    organizer: str | None = None
    domain: str | None = "autre"
    opportunity_type: str | None = "autre"
    summary: str | None = None
    is_actionable: bool = False
    score: int = Field(default=0, ge=0, le=100)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str | None = "to_review"
    country_scope: str | None = None
    ai_provider: str | None = None
    reason: str | None = None
    flags: list[str] = Field(default_factory=list)


class VeilleResponse(BaseModel):
    """Réponse complète du endpoint POST /api/v1/ia/veille/rechercher"""

    query: str
    total_results: int
    opportunities: list[OpportunityResult]
    status: str
    notes: str | None = None