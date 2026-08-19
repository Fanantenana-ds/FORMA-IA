from fastapi import APIRouter, Depends, status, Header, HTTPException

from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import TokenResponse, UserLogin
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user, require_role

router = APIRouter(
    prefix="/auth",
    tags=["Authentification"]
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

@router.get("/me")
def get_me(current_user = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "nom": current_user.nom,
        "email": current_user.email,
        "role": current_user.role
    }

@router.get("/test-direction")
def test_direction(current_user = Depends(require_role("Direction"))):
    return {
        "message": "Accès autorisé",
        "user": current_user.nom,
        "role": current_user.role
    }