from app.services.groq_service import GroqService


class QuestionAnsweringService:

    def __init__(self):

        self.groq = GroqService()

    def answer_question(
        self,
        question: str,
        context: str
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
            context=context
        )

        return answer