from langgraph.graph import StateGraph, END

from app.graph.state import GraphState
from app.graph.nodes import (
    retrieve_articles_node,
    build_context_node,
    generate_answer_node,
)


graph = StateGraph(GraphState)

graph.add_node("retrieve_articles", retrieve_articles_node)
graph.add_node("build_context", build_context_node)
graph.add_node("generate_answer", generate_answer_node)

graph.set_entry_point("retrieve_articles")

graph.add_edge("retrieve_articles", "build_context")
graph.add_edge("build_context", "generate_answer")
graph.add_edge("generate_answer", END)

research_graph = graph.compile()