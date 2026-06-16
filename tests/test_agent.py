from app.agents.research_agent import (
    ResearchAgent
)

agent = ResearchAgent()

response = agent.answer(
    "What are North Korean hackers doing recently?"
)

print(response)