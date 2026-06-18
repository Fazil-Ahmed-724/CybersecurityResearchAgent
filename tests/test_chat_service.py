from app.database.db import SessionLocal

from app.repositories.chat_repository import (
    ChatRepository
)

from app.services.chat_service import (
    ChatService
)

db = SessionLocal()

repository = ChatRepository(
    db
)

service = ChatService(
    repository
)

chat = service.create_chat(
    "North Korean Malware Research"
)

print(
    f"Chat ID: {chat.id}"
)

service.save_user_message(
    chat.id,
    "What is NarwhalRAT?"
)

service.save_assistant_message(
    chat.id,
    "NarwhalRAT is a RAT used in North Korean campaigns."
)

messages = service.get_messages(
    chat.id
)

print("\nMessages\n")

for msg in messages:

    print(
        f"[{msg.role}] {msg.content}"
    )