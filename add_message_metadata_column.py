from sqlalchemy import text
from app.database.db import engine

sql = """
ALTER TABLE messages
ADD COLUMN IF NOT EXISTS metadata_json JSON;
"""

with engine.begin() as connection:
    connection.execute(text(sql))

print("messages.metadata_json column ensured successfully.")