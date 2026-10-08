from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def find_by_id(self, user_id) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def find_all(
        self,
        role: Optional[RoleEnum] = None,
        actif: Optional[bool] = None,
    ) -> List[User]:
        q = self.db.query(User)
        if role is not None:
            q = q.filter(User.role == role)
        if actif is not None:
            q = q.filter(User.actif == actif)
        return q.order_by(User.nom).all()

    def save(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()
    