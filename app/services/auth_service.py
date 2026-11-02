from datetime import UTC, datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.user import RoleEnum, User
from app.repositories.revoked_token_repository import RevokedTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class AuthService:
    def __init__(self, db: Session):
        self.user_repository = UserRepository(db)
        self.revoked_token_repository = (
            RevokedTokenRepository(db)
        )

    def register(self, user_data: UserCreate, owner_id=None):
        existing_user = (
            self.user_repository
            .find_by_email(user_data.email)
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cet email est dÃ©jÃ  associÃ© Ã  un compte"
            )

        hashed_password = hash_password(
            user_data.password
        )

        user = User(
            nom = user_data.nom,
            email = user_data.email,
            password = hashed_password,
            role = user_data.role
        )
        user.owner_id = owner_id
        if user_data.role == RoleEnum.DIRECTION and user.owner_id is None:
            self.user_repository.db.add(user)
            self.user_repository.db.flush()
            user.owner_id = user.id

        return self.user_repository.save(user)

    def create_managed_user(self, user_data: UserCreate, owner_id):
        if user_data.role not in {RoleEnum.ASSISTANT, RoleEnum.COMPTABLE}:
            raise HTTPException(status_code=422, detail="Le directeur peut créer un compte assistant ou comptable. Les comptes formateur sont créés à l’acceptation d’une candidature.")
        existing = self.user_repository.find_by_email(user_data.email)
        if existing:
            raise HTTPException(status_code=400, detail="Cet email est déjà associé à un compte.")
        user = User(
            nom=user_data.nom,
            email=user_data.email,
            password=hash_password(user_data.password),
            role=user_data.role,
            owner_id=owner_id,
        )
        return self.user_repository.save(user)

    def login(self, email: str, password: str):
        user = (
            self.user_repository
            .find_by_email(email)
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou mot de passe incorrect"
            )

        if not verify_password(password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou mot de passe incorrect"
            )

        if not user.actif:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ce compte est dÃ©sactivÃ©"
            )

        token = create_access_token({
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value
        })

        return {
            "access_token": token,
            "token_type": "bearer"
        }

    def logout(self, token: str):
        payload = decode_access_token(token)

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide"
            )

        jti = payload.get("jti")
        user_id = payload.get("sub")
        exp = payload.get("exp")

        if not jti or not user_id or not exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide"
            )

        already_revoked = (
            self.revoked_token_repository
            .exist_by_jti(jti)
        )

        if already_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token dÃ©jÃ  rÃ©voquÃ©"
            )

        expire_at = datetime.fromtimestamp(exp, tz=UTC)

        self.revoked_token_repository.save(
            jti = jti,
            user_id = user_id,
            expire_at = expire_at
        )

        return {"message": "DÃ©connexion rÃ©ussie"}

    # -------------------------------------------------------------------------
    # ADMIN â€” gestion des utilisateurs (DIRECTION uniquement)
    # -------------------------------------------------------------------------

    def lister_utilisateurs(
        self,
        role: RoleEnum | None = None,
        actif: bool | None = None,
        owner_id=None,
    ) -> list[User]:
        return self.user_repository.find_all(role=role, actif=actif, owner_id=owner_id)

    def _get_user_or_404(self, user_id: UUID, owner_id=None) -> User:
        user = self.user_repository.find_by_id_for_owner(user_id, owner_id) if owner_id else self.user_repository.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        return user

    def get_utilisateur(self, user_id: UUID, owner_id=None) -> User:
        return self._get_user_or_404(user_id, owner_id)

    def mettre_a_jour_utilisateur(self, user_id: UUID, data: UserUpdate, owner_id=None) -> User:
        user = self._get_user_or_404(user_id, owner_id)
        updates = data.model_dump(exclude_none=True)
        if user.role == RoleEnum.DIRECTION and "role" in updates:
            raise HTTPException(status_code=422, detail="Le rôle du compte Directeur principal ne peut pas être modifié.")
        if updates.get("role") in {RoleEnum.DIRECTION, RoleEnum.FORMATEUR}:
            raise HTTPException(status_code=422, detail="Les comptes Directeur sont créés à l’ouverture de l’entreprise et les comptes formateur à l’acceptation d’une candidature.")
        if "email" in updates:
            existing = self.user_repository.find_by_email(updates["email"])
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=400,
                    detail="Cet email est dÃ©jÃ  associÃ© Ã  un autre compte.",
                )
        for field, value in updates.items():
            setattr(user, field, value)
        return self.user_repository.save(user)

    def supprimer_utilisateur(self, user_id: UUID, current_user_id: UUID, owner_id=None) -> None:
        if user_id == current_user_id:
            raise HTTPException(
                status_code=400,
                detail="Impossible de supprimer son propre compte.",
            )
        user = self._get_user_or_404(user_id, owner_id)
        self.user_repository.delete(user)

