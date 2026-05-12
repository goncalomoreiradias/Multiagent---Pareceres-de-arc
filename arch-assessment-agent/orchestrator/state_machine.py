import os
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state.context_schema import GraphState
from agents.intake_agent import run_intake
from agents.impact_agent import run_impact_analysis
from agents.question_agent import run_question_loop
from agents.context_builder import run_context_build
from agents.architect_reasoner import run_reasoning
from agents.architect_writer import run_writing
from agents.diagram_agent import run_diagram_gen
from agents.reviewer_agent import run_review
from agents.finalizer import run_reshape, run_finalize

from config import config


def question_router(state: GraphState) -> str:
    """Routes based on question rounds and confidence."""
    context = state["context"]
    if context.context_confidence >= config.CONFIDENCE_THRESHOLD or context.question_rounds >= config.MAX_QUESTION_ROUNDS:
        return "context_builder"
    return "ask_human"  # Pause before this node to let the UI collect answers

def ask_human(state: GraphState) -> dict:
    """Dummy node to represent human input collection."""
    return {"current_agent": "ask_human"}


def user_feedback_router(state: GraphState) -> str:
    """Routes based on user feedback after review."""
    user_feedback = state.get("user_feedback", "")
    # Normalise: LangGraph can merge state into list in some edge cases
    if isinstance(user_feedback, list):
        user_feedback = " ".join(str(v) for v in user_feedback)
    user_feedback = str(user_feedback or "")
    if user_feedback.strip() != "":
        return "finalizer_reshape"
    return "finalizer_complete"


def build_graph():
    """Builds the LangGraph state machine."""
    workflow = StateGraph(GraphState)

    # 1. Add all nodes
    workflow.add_node("intake", run_intake)
    workflow.add_node("impact", run_impact_analysis)
    workflow.add_node("question_agent", run_question_loop)
    workflow.add_node("ask_human", ask_human)
    workflow.add_node("context_builder", run_context_build)
    workflow.add_node("reasoner", run_reasoning)
    workflow.add_node("writer", run_writing)
    workflow.add_node("diagrams", run_diagram_gen)
    workflow.add_node("reviewer", run_review)
    workflow.add_node("finalizer_reshape", run_reshape)
    workflow.add_node("finalizer_complete", run_finalize)

    # 2. Add edges
    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "impact")
    workflow.add_edge("impact", "question_agent")

    # Conditional edge for question loop
    # If confidence is high enough → proceed to context_builder
    # Otherwise → interrupt so the UI can collect user answers
    workflow.add_conditional_edges(
        "question_agent",
        question_router,
        {
            "context_builder": "context_builder",
            "ask_human": "ask_human"
        }
    )
    workflow.add_edge("ask_human", "question_agent")

    workflow.add_edge("context_builder", "reasoner")
    workflow.add_edge("reasoner", "writer")
    workflow.add_edge("writer", "diagrams")
    workflow.add_edge("diagrams", "reviewer")

    # After reviewer, pause for human-in-the-loop feedback
    workflow.add_conditional_edges(
        "reviewer",
        user_feedback_router,
        {
            "finalizer_reshape": "finalizer_reshape",
            "finalizer_complete": "finalizer_complete"
        }
    )

    workflow.add_edge("finalizer_reshape", "finalizer_complete")
    workflow.add_edge("finalizer_complete", END)

    # Use MemorySaver for checkpoints
    memory = MemorySaver()

    # Interrupt BEFORE ask_human (to collect answers) and AFTER reviewer (to collect feedback)
    return workflow.compile(checkpointer=memory, interrupt_before=["ask_human"], interrupt_after=["reviewer"])
