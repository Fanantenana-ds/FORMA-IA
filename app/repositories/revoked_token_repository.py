from datetime import datetime

from sqlalchemy.orm import Session

from app.models.revoked_token import RevokedToken

class RevokedTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, jti: str, user_id, expire_at: datetime) -> RevokedToken:
        revoked_token = RevokedToken(
            jti = jti,
            user_id = user_id,
            expire_at = expire_at
        )

        self.db.add(revoked_token)
        self.db.commit()
        self.db.refresh(revoked_token)

        return revoked_token

    def exist_by_jti(self, jti: str) -> bool:
        token = (
            self.db.query(RevokedToken)
            .filter(
                RevokedToken.jti == jti
            )
            .first()
        )

        return token is not None