from app.database.db import engine
from app.database.base import Base

# Import models
from app.models.user import User
from app.models.chat import Chat
from app.models.message import Message


def create_tables():

    Base.metadata.create_all(
        bind=engine
    )

    print(
        "Phase 15 tables created successfully."
    )


if __name__ == "__main__":

    create_tables()