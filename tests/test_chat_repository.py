from app.database.db import SessionLocal

from app.repositories.chat_repository import (
    ChatRepository
)

db = SessionLocal()

repo = ChatRepository(db)

chat = repo.create_chat(
    "North Korean Malware Research"
)

print(
    f"Chat Created: {chat.id}"
)

repo.save_message(
    chat.id,
    "user",
    "What is NarwhalRAT?"
)

repo.save_message(
    chat.id,
    "assistant",
    "NarwhalRAT is..."
)

messages = repo.get_messages(
    chat.id
)

for msg in messages:

    print(
        msg.role,
        msg.content
    )