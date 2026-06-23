from app.database.db import engine
from app.models.ingestion_run import IngestionRun
from app.database.base import Base


def main():
    Base.metadata.create_all(bind=engine, tables=[IngestionRun.__table__])
    print("ingestion_runs table created successfully.")


if __name__ == "__main__":
    main()