# app/api/v1/endpoints/rh.py
# ============================================================
# ROUTES BACKEND — M4 RH (Formateurs, Candidats, Entretiens)
# ============================================================
#
# FORMATEURS (prestataires externes)
#   POST   /rh/formateurs                         Créer un formateur
#   GET    /rh/formateurs                         Lister (filtres : specialite, statut)
#   GET    /rh/formateurs/{id}                    Lire un formateur
#   PATCH  /rh/formateurs/{id}                    Mettre à jour (score, statut, tarif…)
#   DELETE /rh/formateurs/{id}                    Supprimer un formateur
#
# CANDIDATS (présélection + entretiens)
#   POST   /rh/candidats                          Créer un dossier candidat
#   GET    /rh/candidats                          Lister (filtres : poste_vise, decision)
#   GET    /rh/candidats/{id}                     Lire un dossier candidat
#   PATCH  /rh/candidats/{id}                     Mettre à jour (décision, score…)
#   DELETE /rh/candidats/{id}                     Supprimer un dossier candidat
#
# ENTRETIENS (sous-ressource de Candidat)
#   POST   /rh/candidats/{id}/entretiens          Créer un entretien
#   GET    /rh/candidats/{id}/entretiens          Lister les entretiens d'un candidat
#   GET    /rh/entretiens/{id}                    Lire un entretien
#   PATCH  /rh/entretiens/{id}                    Mettre à jour (CR, email, décision…)
#   DELETE /rh/entretiens/{id}                    Supprimer un entretien
#
# ⚙️  Rôles :
#   Lecture  → tout utilisateur authentifié (get_current_user)
#   Écriture → DIRECTION, ADMIN
# ============================================================

from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.rh import (
    FormateurCreate, FormateurUpdate, FormateurResponse,
    CandidatCreate, CandidatUpdate, CandidatResponse,
    EntretienCreate, EntretienUpdate, EntretienResponse,
)
from app.services.rh_service import RhService

router = APIRouter(prefix="/rh", tags=["M4 — RH Backend"])


def get_rh_service(db: Session = Depends(get_db)) -> RhService:
    return RhService(db)


# =============================================================================
# FORMATEURS
# =============================================================================

@router.post(
    "/formateurs",
    response_model=FormateurResponse,
    status_code=201,
    summary="Créer un formateur externe",
    description=(
        "Crée un nouveau dossier formateur (prestataire externe récurrent).\n\n"
        "**Champ obligatoire :** `nom`.\n\n"
        "**Champs optionnels :** `prenom`, `email`, `telephone`, `adresse`, "
        "`specialite`, `tarif_journalier`, `notes_internes`.\n\n"
        "**Rôles autorisés :** DIRECTION, ADMIN."
    ),
)
def creer_formateur(
    data: FormateurCreate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.creer_formateur(data)


@router.get(
    "/formateurs",
    response_model=List[FormateurResponse],
    summary="Lister les formateurs",
    description=(
        "Retourne tous les formateurs, triés par nom.\n\n"
        "**Filtres optionnels :**\n"
        "- `specialite` : recherche partielle insensible à la casse\n"
        "- `statut` : `DISPONIBLE` | `OCCUPE` | `INACTIF`\n\n"
        "**Exemple :** `GET /rh/formateurs?statut=DISPONIBLE&specialite=IA`\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def lister_formateurs(
    specialite: Optional[str] = Query(default=None, description="Filtrer par spécialité (partiel)"),
    statut: Optional[str] = Query(default=None, description="Filtrer par statut (DISPONIBLE|OCCUPE|INACTIF)"),
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_formateurs(specialite=specialite, statut=statut)


@router.get(
    "/formateurs/{formateur_id}",
    response_model=FormateurResponse,
    summary="Lire un formateur par son ID",
    description=(
        "Retourne les détails d'un formateur identifié par son UUID.\n\n"
        "Retourne **404** si le formateur n'existe pas.\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def get_formateur(
    formateur_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_formateur(formateur_id)


@router.patch(
    "/formateurs/{formateur_id}",
    response_model=FormateurResponse,
    summary="Mettre à jour un formateur (PATCH partiel)",
    description=(
        "Modifie un ou plusieurs champs d'un formateur existant.\n\n"
        "**Tous les champs sont optionnels** (PATCH semantics).\n\n"
        "**Champs modifiables :** `nom`, `prenom`, `email`, `telephone`, `adresse`, "
        "`specialite`, `tarif_journalier`, `statut`, `score_moyen`, `nb_sessions`, "
        "`recommandation`, `notes_internes`.\n\n"
        "Le champ `score_moyen` est mis à jour automatiquement par l'Agent 5 (M5 — évaluation "
        "post-session) via la route de synchronisation IA.\n\n"
        "Retourne **404** si le formateur n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, ADMIN."
    ),
)
def mettre_a_jour_formateur(
    formateur_id: UUID,
    data: FormateurUpdate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.mettre_a_jour_formateur(formateur_id, data)


@router.delete(
    "/formateurs/{formateur_id}",
    status_code=204,
    summary="Supprimer un formateur",
    description=(
        "Supprime définitivement un formateur et ses candidatures associées (cascade).\n\n"
        "⚠️ **Action irréversible.**\n\n"
        "Retourne **404** si le formateur n'existe pas.\n\n"
        "Retourne **204 No Content** en cas de succès.\n\n"
        "**Rôles autorisés :** DIRECTION, ADMIN."
    ),
)
def supprimer_formateur(
    formateur_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    service.supprimer_formateur(formateur_id)


# =============================================================================
# CANDIDATS
# =============================================================================

@router.post(
    "/candidats",
    response_model=CandidatResponse,
    status_code=201,
    summary="Créer un dossier candidat",
    description=(
        "Crée un nouveau dossier de présélection pour un candidat.\n\n"
        "**Champs obligatoires :** `nom`, `poste_vise`.\n\n"
        "**Champs optionnels :** `cv_texte`, `score_preselection`, "
        "`decision_preselection`, `review_id_preselection`, `formateur_id`.\n\n"
        "Ce dossier est typiquement créé automatiquement par la route de synchronisation "
        "IA (A1 — présélection) après approbation HITL.\n\n"
        "**Rôles autorisés :** DIRECTION, ADMIN."
    ),
)
def creer_candidat(
    data: CandidatCreate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.creer_candidat(data)


@router.get(
    "/candidats",
    response_model=List[CandidatResponse],
    summary="Lister les dossiers candidats",
    description=(
        "Retourne tous les dossiers candidats, triés par date de création décroissante.\n\n"
        "**Filtres optionnels :**\n"
        "- `poste_vise` : recherche partielle insensible à la casse\n"
        "- `decision` : `RETENU` | `A_DISCUTER` | `NON_RETENU`\n\n"
        "**Exemple :** `GET /rh/candidats?decision=RETENU`\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def lister_candidats(
    poste_vise: Optional[str] = Query(default=None, description="Filtrer par poste visé (partiel)"),
    decision: Optional[str] = Query(default=None, description="Filtrer par décision de présélection"),
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_candidats(poste_vise=poste_vise, decision=decision)


@router.get(
    "/candidats/{candidat_id}",
    response_model=CandidatResponse,
    summary="Lire un dossier candidat",
    description=(
        "Retourne les détails d'un dossier candidat identifié par son UUID.\n\n"
        "Retourne **404** si le candidat n'existe pas.\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def get_candidat(
    candidat_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_candidat(candidat_id)


@router.patch(
    "/candidats/{candidat_id}",
    response_model=CandidatResponse,
    summary="Mettre à jour un dossier candidat (PATCH partiel)",
    description=(
        "Modifie un ou plusieurs champs d'un dossier candidat.\n\n"
        "**Champs modifiables :** `score_preselection`, `decision_preselection`, "
        "`review_id_preselection`, `formateur_id`.\n\n"
        "Retourne **404** si le candidat n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, ADMIN."
    ),
)
def mettre_a_jour_candidat(
    candidat_id: UUID,
    data: CandidatUpdate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.mettre_a_jour_candidat(candidat_id, data)


@router.delete(
    "/candidats/{candidat_id}",
    status_code=204,
    summary="Supprimer un dossier candidat",
    description=(
        "Supprime définitivement un dossier candidat et tous ses entretiens associés (cascade).\n\n"
        "⚠️ **Action irréversible.**\n\n"
        "Retourne **404** si le candidat n'existe pas.\n\n"
        "Retourne **204 No Content** en cas de succès.\n\n"
        "**Rôles autorisés :** DIRECTION, ADMIN."
    ),
)
def supprimer_candidat(
    candidat_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    service.supprimer_candidat(candidat_id)


# =============================================================================
# ENTRETIENS (sous-ressource de Candidat)
# =============================================================================

@router.post(
    "/candidats/{candidat_id}/entretiens",
    response_model=EntretienResponse,
    status_code=201,
    summary="Créer un entretien pour un candidat",
    description=(
        "Crée un entretien associé à un dossier candidat.\n\n"
        "**Tous les champs sont optionnels** — l'entretien peut être créé vide "
        "puis enrichi via PATCH.\n\n"
        "**Champs disponibles :** `date_entretien`, `interviewers` (CSV), "
        "`notes_brutes`, `compte_rendu` (JSON sérialisé), `decision`, "
        "`review_id_entretien`, `email_brouillon` (JSON sérialisé), `review_id_email`.\n\n"
        "Retourne **404** si le candidat n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, ADMIN."
    ),
)
def creer_entretien(
    candidat_id: UUID,
    data: EntretienCreate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.creer_entretien(candidat_id, data)


@router.get(
    "/candidats/{candidat_id}/entretiens",
    response_model=List[EntretienResponse],
    summary="Lister les entretiens d'un candidat",
    description=(
        "Retourne tous les entretiens d'un candidat, triés par date de création décroissante.\n\n"
        "Retourne **404** si le candidat n'existe pas.\n\n"
        "Retourne une liste vide si aucun entretien n'a encore été créé.\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def lister_entretiens(
    candidat_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_entretiens(candidat_id)


@router.get(
    "/entretiens/{entretien_id}",
    response_model=EntretienResponse,
    summary="Lire un entretien par son ID",
    description=(
        "Retourne les détails complets d'un entretien identifié par son UUID.\n\n"
        "Retourne **404** si l'entretien n'existe pas.\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def get_entretien(
    entretien_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_entretien(entretien_id)


@router.patch(
    "/entretiens/{entretien_id}",
    response_model=EntretienResponse,
    summary="Mettre à jour un entretien (PATCH partiel)",
    description=(
        "Modifie un ou plusieurs champs d'un entretien existant.\n\n"
        "**Tous les champs sont optionnels** (PATCH semantics).\n\n"
        "**Champs modifiables :** `date_entretien`, `interviewers`, `notes_brutes`, "
        "`compte_rendu`, `decision` (`RECRUTER` | `APPROFONDIR` | `NE_PAS_RECRUTER`), "
        "`review_id_entretien`, `email_brouillon`, `review_id_email`.\n\n"
        "Le champ `compte_rendu` et `email_brouillon` sont des JSON sérialisés en string, "
        "produits par l'IA (A2 — CR entretien, A3 — brouillon email).\n\n"
        "Retourne **404** si l'entretien n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, ADMIN."
    ),
)
def mettre_a_jour_entretien(
    entretien_id: UUID,
    data: EntretienUpdate,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    return service.mettre_a_jour_entretien(entretien_id, data)


@router.delete(
    "/entretiens/{entretien_id}",
    status_code=204,
    summary="Supprimer un entretien",
    description=(
        "Supprime définitivement un entretien.\n\n"
        "⚠️ **Action irréversible.**\n\n"
        "Retourne **404** si l'entretien n'existe pas.\n\n"
        "Retourne **204 No Content** en cas de succès.\n\n"
        "**Rôles autorisés :** DIRECTION, ADMIN."
    ),
)
def supprimer_entretien(
    entretien_id: UUID,
    service: RhService = Depends(get_rh_service),
    current_user: User = Depends(require_role("DIRECTION", "ADMIN")),
):
    service.supprimer_entretien(entretien_id)
