from groq import Groq
from app.config.settings import settings

client = Groq(
    api_key=settings.GROQ_API_KEY
)

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {
            "role": "user",
            "content": "Say hello"
        }
    ]
)

print(response.choices[0].message.content)