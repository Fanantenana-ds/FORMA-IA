# app/schemas/rag_ia.py
# ============================================================
# SCHÉMAS Pydantic — Module RAG (C3)
# ============================================================

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    formation_code: str | None = None


class ChatSource(BaseModel):
    fichier: str | None = None
    formation: str | None = None
    page: int | None = None
    score: float | None = None
    url: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    type_reponse: str
    reponse: str
    sources: list[dict[str, Any]] = []
    formation_resolue: str | None = None
    suggestions: list[str] = []
    duree_ms: float


class FormationResume(BaseModel):
    code: str
    titre: str
    domaine: str | None = None
    nb_supports_indexes: int = 0


# ============================================================
# ÉTAPE G — Portfolio, syllabus, questions
# ============================================================

class GenererPortfolioRequest(BaseModel):
    domaine: str | None = Field(None, description="Filtre optionnel par domaine")
    reference_ao: str | None = Field(None, description="Référence de l'appel d'offres visé")


class ModuleSyllabus(BaseModel):
    titre: str
    duree: str = Field(..., description="Ex: '3h' ou '1 jour'")
    contenus: str | None = None
    methodes: str | None = None
    objectif_lie: str | None = None


class GenererSyllabusRequest(BaseModel):
    formation_code: str
    modules: list[ModuleSyllabus] = Field(..., min_length=1)
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="format, public_cible, prerequis, effectif_recommande, langue, lieu, prepare_pour",
    )


class GenererQuestionsRequest(BaseModel):
    formation_code: str
    nb_questions_max: int = Field(10, ge=1, le=30)


# ============================================================
# ÉTAPE H — Ingestion en arrière-plan, recherche, statut
# ============================================================

class IndexerDocumentRequest(BaseModel):
    chemin_fichier: str = Field(
        ..., description="Chemin local du fichier déjà présent sur le disque du service IA (pas d'upload multipart)."
    )
    formation_code: str | None = None
    collection: str = "support"


class RechercherRequest(BaseModel):
    requete: str = Field(..., min_length=1)
    top_k: int | None = Field(None, ge=1, le=50)
    collection: str = "support"
    formation_code: str | None = None
    domaine: str | None = None
    annee: int | None = None
    type_support: str | None = None
    seuil_min: float | None = Field(None, ge=0.0, le=1.0)
