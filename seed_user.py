from app.database.db import SessionLocal
from app.models.user import User

db = SessionLocal()

existing_user = (
    db.query(User)
    .filter(
        User.email == "nafil@example.com"
    )
    .first()
)

if existing_user:

    print(
        f"User already exists: {existing_user.id}"
    )

else:

    user = User(
        name="Nafil Ahmed",
        email="nafil@example.com",
        password_hash="dummy-password"
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    print(
        f"User created: {user.id}"
    )

db.close()