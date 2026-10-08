# app/schemas/rag_ia.py
# ============================================================
# SCHÉMAS Pydantic — Module RAG (C3)
# ============================================================

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    formation_code: Optional[str] = None


class ChatSource(BaseModel):
    fichier: Optional[str] = None
    formation: Optional[str] = None
    page: Optional[int] = None
    score: Optional[float] = None
    url: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    type_reponse: str
    reponse: str
    sources: List[Dict[str, Any]] = []
    formation_resolue: Optional[str] = None
    suggestions: List[str] = []
    duree_ms: float


class FormationResume(BaseModel):
    code: str
    titre: str
    domaine: Optional[str] = None
    nb_supports_indexes: int = 0


# ============================================================
# ÉTAPE G — Portfolio, syllabus, questions
# ============================================================

class GenererPortfolioRequest(BaseModel):
    domaine: Optional[str] = Field(None, description="Filtre optionnel par domaine")
    reference_ao: Optional[str] = Field(None, description="Référence de l'appel d'offres visé")


class ModuleSyllabus(BaseModel):
    titre: str
    duree: str = Field(..., description="Ex: '3h' ou '1 jour'")
    contenus: Optional[str] = None
    methodes: Optional[str] = None
    objectif_lie: Optional[str] = None


class GenererSyllabusRequest(BaseModel):
    formation_code: str
    modules: List[ModuleSyllabus] = Field(..., min_length=1)
    options: Dict[str, Any] = Field(
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
    formation_code: Optional[str] = None
    collection: str = "support"


class RechercherRequest(BaseModel):
    requete: str = Field(..., min_length=1)
    top_k: Optional[int] = Field(None, ge=1, le=50)
    collection: str = "support"
    formation_code: Optional[str] = None
    domaine: Optional[str] = None
    annee: Optional[int] = None
    type_support: Optional[str] = None
    seuil_min: Optional[float] = Field(None, ge=0.0, le=1.0)
