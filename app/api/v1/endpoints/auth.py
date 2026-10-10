from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.user import RoleEnum
from app.schemas.auth import TokenResponse, UserLogin
from app.schemas.user import UserAdminResponse, UserCreate, UserResponse, UserUpdate
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Authentification"],
)

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    service = AuthService(db)

    return service.register(user_data)

@router.post(
    "/login",
    response_model=TokenResponse
)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    service = AuthService(db)

    return service.login(
        email = user_data.email,
        password = user_data.password
    )

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK
)
def logout(authorization: str = Header(...), db: Session = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer requis"
        )

    token = authorization.replace(
        "Bearer ",
        "",
        1
    )

    service = AuthService(db)

    return service.logout(token)

@router.get(
    "/me",
    summary="Lire son propre profil",
    description="Retourne les informations de l'utilisateur actuellement connecté (id, nom, email, rôle).",
)
def get_me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "nom": current_user.nom,
        "email": current_user.email,
        "role": current_user.role,
    }


# =============================================================================
# GESTION DES UTILISATEURS — réservé DIRECTION
# =============================================================================

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.get(
    "/users",
    response_model=list[UserAdminResponse],
    summary="Lister tous les comptes utilisateurs",
    description=(
        "Retourne la liste de tous les comptes, triés par nom.\n\n"
        "**Filtres optionnels :**\n"
        "- `role` : `DIRECTION` | `ASSISTANT` | `COMPTABLE` | `FORMATEUR`\n"
        "- `actif` : `true` (comptes actifs) | `false` (comptes désactivés)\n\n"
        "**Exemple :** `GET /auth/users?role=FORMATEUR&actif=true`\n\n"
        "**Rôles autorisés :** DIRECTION."
    ),
)
def lister_utilisateurs(
    role: Optional[RoleEnum] = Query(default=None, description="Filtrer par rôle"),
    actif: Optional[bool] = Query(default=None, description="Filtrer par statut actif/inactif"),
    service: AuthService = Depends(get_auth_service),
    current_user=Depends(require_role("DIRECTION")),
):
    return service.lister_utilisateurs(role=role, actif=actif)


@router.get(
    "/users/{user_id}",
    response_model=UserAdminResponse,
    summary="Lire un compte utilisateur par son ID",
    description=(
        "Retourne les détails d'un compte identifié par son UUID.\n\n"
        "Retourne **404** si l'utilisateur n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION."
    ),
)
def get_utilisateur(
    user_id: UUID,
    service: AuthService = Depends(get_auth_service),
    current_user=Depends(require_role("DIRECTION")),
):
    return service.get_utilisateur(user_id)


@router.patch(
    "/users/{user_id}",
    response_model=UserAdminResponse,
    summary="Mettre à jour un compte utilisateur (PATCH partiel)",
    description=(
        "Modifie un ou plusieurs champs d'un compte existant.\n\n"
        "**Tous les champs sont optionnels** (PATCH semantics).\n\n"
        "**Champs modifiables :**\n"
        "- `nom` : nouveau nom d'affichage\n"
        "- `email` : nouvel email (doit être unique — 400 si déjà utilisé)\n"
        "- `role` : `DIRECTION` | `ASSISTANT` | `COMPTABLE` | `FORMATEUR`\n"
        "- `actif` : `false` pour désactiver le compte sans le supprimer "
        "(l'utilisateur ne pourra plus se connecter)\n\n"
        "Retourne **404** si l'utilisateur n'existe pas.\n\n"
        "**Rôles autorisés :** DIRECTION."
    ),
)
def mettre_a_jour_utilisateur(
    user_id: UUID,
    data: UserUpdate,
    service: AuthService = Depends(get_auth_service),
    current_user=Depends(require_role("DIRECTION")),
):
    return service.mettre_a_jour_utilisateur(user_id, data)


@router.delete(
    "/users/{user_id}",
    status_code=204,
    summary="Supprimer un compte utilisateur",
    description=(
        "Supprime définitivement un compte utilisateur.\n\n"
        "⚠️ **Action irréversible.**\n\n"
        "Retourne **400** si vous tentez de supprimer votre propre compte.\n\n"
        "Retourne **404** si l'utilisateur n'existe pas.\n\n"
        "Retourne **204 No Content** en cas de succès.\n\n"
        "💡 Pour désactiver temporairement un compte sans le supprimer, "
        "utilisez `PATCH /auth/users/{id}` avec `{ \"actif\": false }`.\n\n"
        "**Rôles autorisés :** DIRECTION."
    ),
)
def supprimer_utilisateur(
    user_id: UUID,
    service: AuthService = Depends(get_auth_service),
    current_user=Depends(require_role("DIRECTION")),
):
    service.supprimer_utilisateur(user_id, current_user_id=current_user.id)
