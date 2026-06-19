from app.services.groq_service import GroqService


class QuestionAnsweringService:

    def __init__(self):

        self.groq = GroqService()

    def answer_question(
        self,
        question: str,
        context: str,
        chat_history: str = ""
    ):

        print("=" * 50)
        print("QUESTION")
        print(question)

        print("=" * 50)
        print("CONTEXT LENGTH")
        print(len(context))

        print("=" * 50)
        print("CALLING GROQ")

        answer = self.groq.answer_question(
            question=question,
            context=context,
            chat_history=chat_history
        )

        return answer

    def rewrite_query(
        self,
        question: str,
        chat_history: str = ""
    ):

        return self.groq.rewrite_query(
            question=question,
            chat_history=chat_history
        )
