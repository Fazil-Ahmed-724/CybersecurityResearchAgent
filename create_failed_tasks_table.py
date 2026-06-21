from app.database.base import Base
from app.database.db import engine

# Import model so SQLAlchemy metadata knows about it
from app.models.failed_task import FailedTask  # noqa: F401


def create_failed_tasks_table():
    Base.metadata.create_all(bind=engine)
    print("failed_tasks table created successfully.")


if __name__ == "__main__":
    create_failed_tasks_table()