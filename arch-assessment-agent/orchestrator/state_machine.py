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
from agents.finalizer import run_reshape, run_finalize, run_ai_correct

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

def ask_human_review(state: GraphState) -> dict:
    """Dummy node to represent human review input collection."""
    return {"current_agent": "ask_human_review"}

def ai_corrector_router(state: GraphState) -> str:
    """Routes based on AI reviewer approval and run count."""
    context = state["context"]
    if not context.reviewer_approved and context.reviewer_run_count <= 1:
        return "ai_corrector"
    return "ask_human_review"


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


def reshape_router(state: GraphState) -> str:
    """Determines if the user's feedback or report edits require diagram updates."""
    user_feedback = state.get("user_feedback", "")
    if isinstance(user_feedback, list):
        user_feedback = " ".join(str(v) for v in user_feedback)
    user_feedback = str(user_feedback or "")
    
    if not user_feedback.strip():
        return "reviewer"
        
    prompt = f"""
    Analyze the user's feedback on an architecture assessment report.
    Determine if the feedback requires updating or recreating any of the architecture diagrams (Sequence Diagram, Flowchart, or ArchiMate 3.2 Capabilities Diagram).
    
    Feedback affects diagrams if:
    - The user explicitly requests changes to a diagram (e.g., "muda a cor", "adiciona o bloco X ao diagrama", "corrige a sequência", "atualiza o ArchiMate").
    - The user requests structural or flow changes to the solution (e.g., "a autenticação deve passar por Y em vez de Z", "adiciona um novo sistema de base de dados ODL").
    - The user requests changes to systems/integrations that are represented in the diagrams.
    
    Feedback does NOT affect diagrams if:
    - It only requests textual corrections, typos, terminology adjustments, adding descriptions, assumptions, risks, or text-only details.
    
    User Feedback:
    {user_feedback}
    
    Respond with EXACTLY one of the following JSON fields (nothing else):
    {{
        "affects_diagrams": true or false,
        "reason": "short explanation in English"
    }}
    """
    try:
        from langchain_core.messages import HumanMessage
        from tools.response_parser import extract_json_text
        import json
        llm = config.get_llm("gemini")
        res = llm.invoke([HumanMessage(content=prompt)])
        data = json.loads(extract_json_text(res.content))
        if data.get("affects_diagrams", False):
            return "diagrams"
    except Exception:
        # Safe fallback: if LLM check fails, go to reviewer
        pass
        
    return "reviewer"


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
    workflow.add_node("diagrams", run_diagram_gen)
    workflow.add_node("writer", run_writing)
    workflow.add_node("reviewer", run_review)
    workflow.add_node("ai_corrector", run_ai_correct)
    workflow.add_node("ask_human_review", ask_human_review)
    workflow.add_node("finalizer_reshape", run_reshape)
    workflow.add_node("finalizer_complete", run_finalize)

    # 2. Add edges
    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "impact")
    workflow.add_edge("impact", "question_agent")

    # Conditional edge for question loop
    workflow.add_conditional_edges(
        "question_agent",
        question_router,
        {
            "context_builder": "context_builder",
            "ask_human": "ask_human"
        }
    )
    workflow.add_edge("ask_human", "question_agent")

    # High level design workflow: Context -> Reasoning -> Writing -> Diagramming -> Reviewing
    workflow.add_edge("context_builder", "reasoner")
    workflow.add_edge("reasoner", "writer")
    workflow.add_edge("writer", "diagrams")
    workflow.add_edge("diagrams", "reviewer")

    # After reviewer, AI corrects if needed
    workflow.add_conditional_edges(
        "reviewer",
        ai_corrector_router,
        {
            "ai_corrector": "ai_corrector",
            "ask_human_review": "ask_human_review"
        }
    )
    workflow.add_edge("ai_corrector", "ask_human_review")

    # After human review, pause for human-in-the-loop feedback
    workflow.add_conditional_edges(
        "ask_human_review",
        user_feedback_router,
        {
            "finalizer_reshape": "finalizer_reshape",
            "finalizer_complete": "finalizer_complete"
        }
    )

    # If reshaping, check if diagrams need updates
    workflow.add_conditional_edges(
        "finalizer_reshape",
        reshape_router,
        {
            "diagrams": "diagrams",
            "reviewer": "reviewer"
        }
    )
    
    workflow.add_edge("finalizer_complete", END)

    # Use MemorySaver for checkpoints
    memory = MemorySaver()

    # Interrupt BEFORE ask_human and ask_human_review
    return workflow.compile(checkpointer=memory, interrupt_before=["ask_human", "ask_human_review"])
