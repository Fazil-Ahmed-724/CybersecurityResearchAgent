# tests/test_groq_qa.py

from app.services.groq_service import GroqService

groq = GroqService()

answer = groq.answer_question(
    question="What is ransomware?",
    context="""
Ransomware is malware that encrypts files
and demands payment.
"""
)


print(answer)