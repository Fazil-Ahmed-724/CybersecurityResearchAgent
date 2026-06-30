from langgraph.graph import StateGraph, END

from app.graph.state import GraphState

from app.graph.nodes import (
    detect_question_type_node,
    lookup_vulnerability_node,
    retrieve_articles_node,
    build_context_node,
    generate_answer_node,
)


graph = StateGraph(GraphState)

#
# Nodes
#
graph.add_node(
    "detect_question_type",
    detect_question_type_node,
)

graph.add_node(
    "lookup_vulnerability",
    lookup_vulnerability_node,
)

graph.add_node(
    "retrieve_articles",
    retrieve_articles_node,
)

graph.add_node(
    "build_context",
    build_context_node,
)

graph.add_node(
    "generate_answer",
    generate_answer_node,
)


#
# Entry Point
#
graph.set_entry_point(
    "detect_question_type",
)


#
# Conditional Router
#
def route_question(state: GraphState) -> str:

    if state.get("question_type") == "cve_lookup":
        return "lookup_vulnerability"

    return "retrieve_articles"


graph.add_conditional_edges(
    "detect_question_type",
    route_question,
    {
        "lookup_vulnerability": "lookup_vulnerability",
        "retrieve_articles": "retrieve_articles",
    },
)


#
# CVE Route
#
graph.add_edge(
    "lookup_vulnerability",
    "generate_answer",
)


#
# Existing RAG Route
#
graph.add_edge(
    "retrieve_articles",
    "build_context",
)

graph.add_edge(
    "build_context",
    "generate_answer",
)


#
# End
#
graph.add_edge(
    "generate_answer",
    END,
)


research_graph = graph.compile()