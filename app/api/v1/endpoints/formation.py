# app/api/v1/endpoints/formation.py
# ============================================================
# ROUTES BACKEND — Formations (Sessions, Séances, Participants, Inscriptions, Présences)
# ============================================================
#
# SESSIONS
#   POST   /sessions                                  Créer une session de formation
#   GET    /sessions                                  Lister (filtres : formateur_id, client)
#   GET    /sessions/{id}                             Lire une session par ID
#   PATCH  /sessions/{id}                             Modifier une session (PATCH partiel)
#   DELETE /sessions/{id}                             Supprimer une session (cascade séances)
#
# SÉANCES D'UNE SESSION
#   GET    /sessions/{id}/seances                     Lister les séances (ordre chronologique)
#   POST   /sessions/{id}/seances                     Ajouter une séance
#   PATCH  /sessions/seances/{seance_id}              Modifier une séance (date, durée, thème)
#   DELETE /sessions/seances/{seance_id}              Supprimer une séance (cascade présences)
#
# PRÉSENCES D'UNE SÉANCE
#   POST   /sessions/seances/{seance_id}/presences    Enregistrer une présence
#   GET    /sessions/seances/{seance_id}/presences    Lister les présences d'une séance
#   PATCH  /sessions/seances/presences/{presence_id} Corriger le statut d'une présence
#
# INSCRIPTIONS
#   POST   /sessions/{id}/inscrire                    Inscrire un participant
#   DELETE /sessions/{id}/inscrire/{participant_id}   Désinscrire un participant
#   GET    /sessions/{id}/participants                Lister les participants inscrits
#
# PARTICIPANTS (ressource indépendante)
#   POST   /participants                              Créer un participant
#   GET    /participants                              Lister (filtre : nom)
#   GET    /participants/{id}                         Lire un participant par ID
#   PATCH  /participants/{id}                         Modifier un participant (PATCH partiel)
#   DELETE /participants/{id}                         Supprimer un participant
#
# ⚙️  Rôles :
#   Lecture  → tout utilisateur authentifié (get_current_user)
#   Écriture → DIRECTION, FORMATEUR (ou ASSISTANT pour créer un participant)
# ============================================================

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.formation import (
    SeanceCreate, SeanceUpdate, SeanceResponse,
    SessionCreate, SessionUpdate, SessionResponse,
    ParticipantCreate, ParticipantUpdate, ParticipantResponse,
    PresenceCreate, PresenceUpdate, PresenceResponse,
    InscriptionCreate, InscriptionResponse,
)
from app.services.formation_service import FormationService

router = APIRouter(
    prefix="/sessions",
    tags=["Formations"],
)


def get_formation_service(db: DbSession = Depends(get_db)) -> FormationService:
    return FormationService(db)


# =============================================================================
# SESSIONS
# =============================================================================

@router.post(
    "",
    response_model=SessionResponse,
    status_code=201,
    summary="Créer une session de formation",
    description=(
        "Crée une nouvelle session de formation.\n\n"
        "**Champs obligatoires :** `titre`, `date_debut`.\n\n"
        "**Champs optionnels :** `client`, `date_fin` (défaut = `date_debut`), `formateur_id` (UUID d'un utilisateur).\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR."
    ),
)
def creer_session(
    data: SessionCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.creer_session(data)


@router.get(
    "",
    response_model=List[SessionResponse],
    summary="Lister toutes les sessions de formation",
    description=(
        "Retourne toutes les sessions, triées par date de début décroissante.\n\n"
        "**Filtres optionnels :**\n"
        "- `formateur_id` : UUID du formateur assigné à la session.\n"
        "- `client` : filtre partiel sur le nom du client (insensible à la casse).\n\n"
        "**Exemple :** `GET /sessions?client=TELMA`\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def lister_sessions(
    formateur_id: Optional[UUID] = Query(default=None, description="Filtrer par UUID du formateur"),
    client: Optional[str] = Query(default=None, description="Filtrer par nom du client (recherche partielle)"),
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_sessions(formateur_id=formateur_id, client=client)


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Mettre à jour une session (PATCH partiel)",
    description=(
        "Modifie un ou plusieurs champs d'une session existante.\n\n"
        "**Tous les champs sont optionnels** — seuls les champs fournis sont modifiés "
        "(PATCH semantics).\n\n"
        "**Champs modifiables :** `titre`, `client`, `date_debut`, `date_fin`, `formateur_id`.\n\n"
        "Retourne **422** si `date_fin` est antérieure à `date_debut`.\n\n"
        "Retourne **404** si la session n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR."
    ),
)
def mettre_a_jour_session(
    session_id: UUID,
    data: SessionUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.mettre_a_jour_session(session_id, data)


@router.delete(
    "/{session_id}",
    status_code=204,
    summary="Supprimer une session",
    description=(
        "Supprime définitivement une session et toutes ses séances (cascade).\n\n"
        "⚠️ **Action irréversible** : les séances et présences associées sont également supprimées.\n\n"
        "Retourne **404** si la session n'existe pas.\n\n"
        "Retourne **204 No Content** en cas de succès.\n\n"
        "**Rôles autorisés :** DIRECTION."
    ),
)
def supprimer_session(
    session_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    service.supprimer_session(session_id)


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Lire une session par son ID",
    description=(
        "Retourne les détails d'une session identifiée par son UUID.\n\n"
        "Retourne **404** si la session n'existe pas.\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def get_session(
    session_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_session(session_id)


# =============================================================================
# SÉANCES D'UNE SESSION
# =============================================================================

@router.get(
    "/{session_id}/seances",
    response_model=List[SeanceResponse],
    summary="Lister les séances d'une session",
    description=(
        "Retourne toutes les séances de la session, triées par date croissante.\n\n"
        "Retourne **404** si la session n'existe pas.\n\n"
        "Retourne une liste vide si aucune séance n'a encore été créée.\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def lister_seances(
    session_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_seances(session_id)


@router.post(
    "/{session_id}/seances",
    response_model=SeanceResponse,
    status_code=201,
    summary="Ajouter une séance à une session",
    description=(
        "Ajoute une séance (journée) à la session.\n\n"
        "**Champs obligatoires :** `date`.\n\n"
        "**Champs optionnels :** `duree` (ex. `'8h'`, défaut : `'Non précisée'`), "
        "`theme` (sujet de la séance, défaut : `'Non précisé'`).\n\n"
        "Retourne **404** si la session n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR."
    ),
)
def ajouter_seance(
    session_id: UUID,
    data: SeanceCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.ajouter_seance(session_id, data)


@router.patch(
    "/seances/{seance_id}",
    response_model=SeanceResponse,
    summary="Modifier une séance (PATCH partiel)",
    description=(
        "Modifie un ou plusieurs champs d'une séance existante.\n\n"
        "**Tous les champs sont optionnels** (PATCH semantics).\n\n"
        "**Champs modifiables :** `date`, `duree` (ex. `'8h'`), `theme`.\n\n"
        "Retourne **404** si la séance n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR."
    ),
)
def mettre_a_jour_seance(
    seance_id: UUID,
    data: SeanceUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.mettre_a_jour_seance(seance_id, data)


@router.delete(
    "/seances/{seance_id}",
    status_code=204,
    summary="Supprimer une séance",
    description=(
        "Supprime définitivement une séance et toutes ses présences (cascade).\n\n"
        "⚠️ **Action irréversible** : les présences liées à cette séance sont également supprimées.\n\n"
        "Retourne **404** si la séance n'existe pas.\n\n"
        "Retourne **204 No Content** en cas de succès.\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR."
    ),
)
def supprimer_seance(
    seance_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    service.supprimer_seance(seance_id)


# =============================================================================
# PRÉSENCES D'UNE SÉANCE
# =============================================================================

@router.get(
    "/seances/{seance_id}/presences",
    response_model=List[PresenceResponse],
    summary="Lister les présences d'une séance",
    description=(
        "Retourne toutes les présences enregistrées pour une séance donnée.\n\n"
        "Retourne **404** si la séance n'existe pas.\n\n"
        "Retourne une liste vide si aucune présence n'a encore été enregistrée.\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def lister_presences(
    seance_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_presences(seance_id)


@router.patch(
    "/seances/presences/{presence_id}",
    response_model=PresenceResponse,
    summary="Corriger le statut d'une présence (PATCH)",
    description=(
        "Modifie le statut d'une présence existante.\n\n"
        "**Corps de la requête :** `{ \"statut\": \"PRESENT\" | \"ABSENT\" | \"EXCUSE\" }`\n\n"
        "Utile pour corriger une erreur de saisie après coup.\n\n"
        "Retourne **404** si la présence n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR."
    ),
)
def mettre_a_jour_presence(
    presence_id: UUID,
    data: PresenceUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.mettre_a_jour_presence(presence_id, data)


# =============================================================================
# INSCRIPTIONS — inscrire / désinscrire / lister participants d'une session
# =============================================================================

@router.post(
    "/{session_id}/inscrire",
    response_model=InscriptionResponse,
    status_code=201,
    summary="Inscrire un participant à une session",
    description=(
        "Inscrit un participant (déjà créé via `POST /participants`) à une session.\n\n"
        "**Corps de la requête :** `{ \"participant_id\": \"<UUID>\" }`\n\n"
        "Retourne **404** si la session ou le participant n'existe pas.\n\n"
        "Retourne **409** si le participant est déjà inscrit à cette session.\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR."
    ),
)
def inscrire_participant(
    session_id: UUID,
    data: InscriptionCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.inscrire_participant(session_id, data)


@router.delete(
    "/{session_id}/inscrire/{participant_id}",
    status_code=204,
    summary="Désinscrire un participant d'une session",
    description=(
        "Supprime l'inscription d'un participant à une session.\n\n"
        "Retourne **404** si la session ou l'inscription n'existe pas.\n\n"
        "Retourne **204 No Content** en cas de succès (pas de corps de réponse).\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR."
    ),
)
def desinscrire_participant(
    session_id: UUID,
    participant_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    service.desinscrire_participant(session_id, participant_id)


@router.get(
    "/{session_id}/participants",
    response_model=List[ParticipantResponse],
    summary="Lister les participants inscrits à une session",
    description=(
        "Retourne la liste des participants inscrits à la session, triés par nom.\n\n"
        "Retourne **404** si la session n'existe pas.\n\n"
        "Retourne une liste vide si aucun participant n'est encore inscrit.\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def lister_participants_session(
    session_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_participants_session(session_id)


# =============================================================================
# PRÉSENCES
# =============================================================================

@router.post(
    "/seances/{seance_id}/presences",
    response_model=PresenceResponse,
    status_code=201,
    summary="Enregistrer la présence d'un participant à une séance",
    description=(
        "Enregistre la présence (ou absence) d'un participant à une séance.\n\n"
        "**Corps de la requête :**\n"
        "```json\n"
        "{\n"
        "  \"participant_id\": \"<UUID>\",\n"
        "  \"statut\": \"PRESENT\" | \"ABSENT\" | \"EXCUSE\",\n"
        "  \"source\": \"MANUEL\" | \"GOOGLE_FORMS\"   (défaut : MANUEL)\n"
        "}\n"
        "```\n\n"
        "Retourne **404** si la séance n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR."
    ),
)
def enregistrer_presence(
    seance_id: UUID,
    data: PresenceCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR")),
):
    return service.enregistrer_presence(seance_id, data)


# =============================================================================
# PARTICIPANTS (ressource indépendante)
# =============================================================================

participants_router = APIRouter(
    prefix="/participants",
    tags=["Formations"],
)


@participants_router.post(
    "",
    response_model=ParticipantResponse,
    status_code=201,
    summary="Créer un participant",
    description=(
        "Crée un nouveau participant dans le système.\n\n"
        "**Champs obligatoires :** `nom`.\n\n"
        "**Champs optionnels :** `email`, `entreprise`.\n\n"
        "Une fois créé, le participant peut être inscrit à une ou plusieurs sessions "
        "via `POST /sessions/{session_id}/inscrire`.\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR, ASSISTANT."
    ),
)
def creer_participant(
    data: ParticipantCreate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR", "ASSISTANT")),
):
    return service.creer_participant(data)


@participants_router.get(
    "",
    response_model=List[ParticipantResponse],
    summary="Lister tous les participants",
    description=(
        "Retourne tous les participants, triés par nom.\n\n"
        "**Filtre optionnel :** `nom` — recherche partielle insensible à la casse.\n\n"
        "**Exemple :** `GET /participants?nom=Rakoto`\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def lister_participants(
    nom: Optional[str] = Query(default=None, description="Filtrer par nom (recherche partielle)"),
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.lister_participants(nom=nom)


@participants_router.get(
    "/{participant_id}",
    response_model=ParticipantResponse,
    summary="Lire un participant par son ID",
    description=(
        "Retourne les détails d'un participant identifié par son UUID.\n\n"
        "Retourne **404** si le participant n'existe pas.\n\n"
        "**Rôles autorisés :** tout utilisateur authentifié."
    ),
)
def get_participant(
    participant_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(get_current_user),
):
    return service.get_participant(participant_id)


@participants_router.patch(
    "/{participant_id}",
    response_model=ParticipantResponse,
    summary="Modifier un participant (PATCH partiel)",
    description=(
        "Modifie un ou plusieurs champs d'un participant existant.\n\n"
        "**Tous les champs sont optionnels** (PATCH semantics).\n\n"
        "**Champs modifiables :** `nom`, `email`, `entreprise`.\n\n"
        "Retourne **404** si le participant n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION, FORMATEUR, ASSISTANT."
    ),
)
def mettre_a_jour_participant(
    participant_id: UUID,
    data: ParticipantUpdate,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION", "FORMATEUR", "ASSISTANT")),
):
    return service.mettre_a_jour_participant(participant_id, data)


@participants_router.delete(
    "/{participant_id}",
    status_code=204,
    summary="Supprimer un participant",
    description=(
        "Supprime définitivement un participant.\n\n"
        "⚠️ **Action irréversible** : ses présences et inscriptions sont également supprimées.\n\n"
        "Retourne **404** si le participant n'existe pas.\n\n"
        "Retourne **204 No Content** en cas de succès.\n\n"
        "**Rôles autorisés :** DIRECTION."
    ),
)
def supprimer_participant(
    participant_id: UUID,
    service: FormationService = Depends(get_formation_service),
    current_user: User = Depends(require_role("DIRECTION")),
):
    service.supprimer_participant(participant_id)