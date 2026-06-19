from sqlalchemy.orm import Session

from app.models.chat_summary import ChatSummary


class ChatSummaryRepository:

    def __init__(
        self,
        db: Session
    ):
        self.db = db

    def get_summary(
        self,
        chat_id: int
    ):

        return (
            self.db.query(ChatSummary)
            .filter(
                ChatSummary.chat_id == chat_id
            )
            .first()
        )

    def save_summary(
        self,
        chat_id: int,
        summary: str
    ):

        chat_summary = ChatSummary(
            chat_id=chat_id,
            summary=summary
        )

        self.db.add(
            chat_summary
        )

        self.db.commit()

        self.db.refresh(
            chat_summary
        )

        return chat_summary

    def update_summary(
        self,
        chat_id: int,
        summary: str
    ):

        chat_summary = self.get_summary(
            chat_id
        )

        if not chat_summary:

            return self.save_summary(
                chat_id=chat_id,
                summary=summary
            )

        chat_summary.summary = summary

        self.db.commit()

        self.db.refresh(
            chat_summary
        )

        return chat_summary
