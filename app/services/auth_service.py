from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.user import User
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token
)


class AuthService:

    def register_user(
        self,
        name: str,
        email: str,
        password: str
    ):

        db: Session = SessionLocal()

        try:

            existing_user = (
                db.query(User)
                .filter(User.email == email)
                .first()
            )

            if existing_user:
                raise Exception(
                    "Email already registered"
                )

            user = User(
                name=name,
                email=email,
                password_hash=hash_password(
                    password
                )
            )

            db.add(user)
            db.commit()
            db.refresh(user)

            return user

        finally:
            db.close()

    def login_user(
        self,
        email: str,
        password: str
    ):

        db: Session = SessionLocal()

        try:

            user = (
                db.query(User)
                .filter(User.email == email)
                .first()
            )

            if not user:
                return None

            if not verify_password(
                password,
                user.password_hash
            ):
                return None

            token = create_access_token(
                {
                    "user_id": user.id,
                    "email": user.email
                }
            )

            return {
                "access_token": token,
                "token_type": "bearer",
                "user_id": user.id,
                "name": user.name
            }

        finally:
            db.close()