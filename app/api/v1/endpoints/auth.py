from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models.user import RoleEnum
from app.models.user_profile_photo import UserProfilePhoto
from app.schemas.auth import TokenResponse, UserLogin
from app.schemas.user import UserAdminResponse, UserCreate, UserProfileUpdate, UserResponse, UserUpdate
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Authentification"],
)

TAILLE_MAX_PHOTO_PROFIL = 1 * 1024 * 1024
SIGNATURE_JPEG = b"\xff\xd8\xff"
FIN_JPEG = b"\xff\xd9"

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if user_data.role != RoleEnum.DIRECTION:
        raise HTTPException(status_code=403, detail="Les comptes assistants et comptables sont créés par la Direction depuis Gestion des utilisateurs.")
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


@router.patch(
    "/me",
    summary="Mettre à jour son propre profil",
    description="Modifie uniquement le nom ou l’adresse e-mail du compte connecté. Le rôle, le statut et le mot de passe ne sont pas modifiables par cette route.",
)
def mettre_a_jour_mon_profil(
    data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return AuthService(db).mettre_a_jour_profil(current_user, data)


@router.get(
    "/me/photo",
    summary="Lire sa photo de profil",
    description="Retourne la photo JPEG du compte connecté. La photo n'est accessible qu'avec une session authentifiée.",
)
def lire_photo_profil(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    photo = db.query(UserProfilePhoto).filter(UserProfilePhoto.user_id == current_user.id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Aucune photo de profil n’est enregistrée.")
    return Response(
        content=photo.contenu,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store"},
    )


@router.put(
    "/me/photo",
    summary="Mettre à jour sa photo de profil",
    description="Enregistre une photo JPEG compressée (1 Mo maximum) sur le compte connecté.",
)
async def mettre_a_jour_photo_profil(
    fichier: UploadFile = File(..., description="Photo JPEG compressée, 1 Mo maximum"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if fichier.content_type != "image/jpeg":
        raise HTTPException(status_code=415, detail="Format non pris en charge. Envoyez une image JPEG.")

    contenu = await fichier.read(TAILLE_MAX_PHOTO_PROFIL + 1)
    if len(contenu) > TAILLE_MAX_PHOTO_PROFIL:
        raise HTTPException(status_code=413, detail="La photo de profil ne doit pas dépasser 1 Mo.")
    if len(contenu) < 5 or not contenu.startswith(SIGNATURE_JPEG) or not contenu.endswith(FIN_JPEG):
        raise HTTPException(status_code=422, detail="Le fichier reçu n’est pas une image JPEG valide.")

    photo = db.query(UserProfilePhoto).filter(UserProfilePhoto.user_id == current_user.id).first()
    if photo is None:
        photo = UserProfilePhoto(user_id=current_user.id, contenu=contenu)
    else:
        photo.contenu = contenu
    db.add(photo)
    db.commit()
    return {"success": True, "message": "Photo de profil mise à jour."}


@router.delete(
    "/me/photo",
    summary="Supprimer sa photo de profil",
)
def supprimer_photo_profil(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    photo = db.query(UserProfilePhoto).filter(UserProfilePhoto.user_id == current_user.id).first()
    if photo:
        db.delete(photo)
        db.commit()
    return {"success": True, "message": "Photo de profil supprimée."}


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
    role: RoleEnum | None = Query(default=None, description="Filtrer par rôle"),
    actif: bool | None = Query(default=None, description="Filtrer par statut actif/inactif"),
    service: AuthService = Depends(get_auth_service),
    current_user=Depends(require_role("DIRECTION")),
):
    owner_id = current_user.owner_id or current_user.id
    return service.lister_utilisateurs(role=role, actif=actif, owner_id=owner_id)


@router.post(
    "/users",
    response_model=UserAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte de l'entreprise",
)
def creer_utilisateur(
    user_data: UserCreate,
    service: AuthService = Depends(get_auth_service),
    current_user=Depends(require_role("DIRECTION")),
):
    return service.create_managed_user(user_data, owner_id=current_user.owner_id or current_user.id)


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
    return service.get_utilisateur(user_id, owner_id=current_user.owner_id or current_user.id)


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
    return service.mettre_a_jour_utilisateur(user_id, data, owner_id=current_user.owner_id or current_user.id)


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
    service.supprimer_utilisateur(user_id, current_user_id=current_user.id, owner_id=current_user.owner_id or current_user.id)
