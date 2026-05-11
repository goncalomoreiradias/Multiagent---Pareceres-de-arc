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
    return "__interrupt__"  # Pause to let the UI collect answers


def user_feedback_router(state: GraphState) -> str:
    """Routes based on user feedback after review."""
    user_feedback = state.get("user_feedback", "")
    if user_feedback and user_feedback.strip() != "":
        return "finalizer_reshape"
    return "finalizer_complete"


def build_graph():
    """Builds the LangGraph state machine."""
    workflow = StateGraph(GraphState)

    # 1. Add all nodes
    workflow.add_node("intake", run_intake)
    workflow.add_node("impact", run_impact_analysis)
    workflow.add_node("question_agent", run_question_loop)
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
            "__interrupt__": "question_agent"  # Will re-enter after UI provides answers
        }
    )

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

    # Interrupt after question_agent (to collect answers) and after reviewer (to collect feedback)
    return workflow.compile(checkpointer=memory, interrupt_after=["question_agent", "reviewer"])
