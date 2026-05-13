import os
import sys
import json
import re
import io
from langchain_core.messages import HumanMessage
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress_bar import ProgressBar
from rich.text import Text
from state.context_schema import GraphState
from tools.response_parser import extract_json_text
from config import config

# Use a UTF-8 stream wrapper to avoid Windows codepage issues with emoji
_utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
console = Console(file=_utf8_stdout, force_terminal=True)

# Dimension definitions: (key, label, max_weight)
DIMENSIONS = [
    ("business_objective", "Objetivo de negócio definido", 20),
    ("stakeholders", "Stakeholders identificados", 10),
    ("technical_constraints", "Restrições técnicas conhecidas", 20),
    ("integration_points", "Pontos de integração mapeados", 15),
    ("security_requirements", "Requisitos de segurança definidos", 15),
    ("timeline_budget", "Prazo e orçamento conhecidos", 10),
    ("slas", "SLAs definidos", 10),
]


def _get_dimension_icon(score: float, max_weight: float) -> str:
    """Returns ✅, ⚠️ or ❌ based on score percentage of weight."""
    pct = score / max_weight if max_weight > 0 else 0
    if pct >= 0.8:
        return "✅"
    elif pct >= 0.4:
        return "⚠️ "
    else:
        return "❌"


def _build_confidence_bar(confidence: float, width: int = 10) -> str:
    """Build a text-based progress bar: ████████░░"""
    filled = int(confidence * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def display_confidence_panel(
    round_num: int,
    max_rounds: int,
    confidence: float,
    threshold: float,
    dimension_scores: dict,
):
    """Displays a Rich panel showing confidence state after a question round."""
    
    # Build status message
    confidence_pct = int(confidence * 100)
    threshold_pct = int(threshold * 100)
    
    if confidence >= threshold:
        status = Text("AVANÇAR PARA ANÁLISE", style="bold green")
    elif round_num < max_rounds:
        status = Text("NOVA RONDA DE PERGUNTAS", style="bold yellow")
    else:
        status = Text("MÁXIMO DE RONDAS ATINGIDO — A AVANÇAR", style="bold rgb(255,165,0)")
    
    # Build the table
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Info", style="bold", width=40)
    table.add_column("Value", width=30)
    
    table.add_row("Ronda atual:", f"{round_num} de {max_rounds}")
    table.add_row("", "")
    table.add_row(
        "Confiança atual:",
        f"{_build_confidence_bar(confidence)}  {confidence_pct}%"
    )
    table.add_row(
        "Limiar para avançar:",
        f"{'':>22}{threshold_pct}%"
    )
    table.add_row("", "")
    table.add_row("Dimensões avaliadas:", "")
    
    for key, label, max_weight in DIMENSIONS:
        score = dimension_scores.get(key, 0.0)
        icon = _get_dimension_icon(score, max_weight)
        score_display = f"({score:.0f}/{max_weight})"
        table.add_row(f"  {icon} {label}", score_display)
    
    table.add_row("", "")
    table.add_row("Status:", "")
    
    panel = Panel(
        table,
        title="📊 Grau de Confiança do Contexto",
        border_style="cyan",
        padding=(1, 2),
    )
    
    console.print(panel)
    console.print("  Status: ", end="")
    console.print(status)
    console.print()


def run_question_loop(state: GraphState) -> dict:
    """Generates questions to clarify the context. 
    Does NOT ask the user directly — that's handled by the UI layer (Streamlit or CLI).
    This agent only generates questions and evaluates confidence."""
    context = state["context"]
    round_num = context.question_rounds + 1
    print(f"[Question Agent] Evaluating context completeness (Round {round_num})...")

    prompt_path = os.path.join(config.PROMPTS_DIR, "questions.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Build a summary of previously asked questions to avoid repetition
    prev_q_summary = ""
    if context.questions:
        for q in context.questions:
            prev_q_summary += f"- [{q.get('category')}] {q.get('question')}\n"
    else:
        prev_q_summary = "(none yet)"

    formatted_prompt = (
        prompt_template
        .replace("{request_type}", str(context.request_type or "UNKNOWN"))
        .replace("{project_name}", context.project_name)
        .replace("{brief_description}", context.brief_description)
        .replace("{impacted_systems}", json.dumps(context.impacted_systems, ensure_ascii=False))
        .replace("{raw_input}", context.raw_input[:3000])  # Cap to save tokens
        .replace("{previous_questions}", prev_q_summary)
    )

    llm = config.get_llm("gemini_pro")
    response = llm.invoke([HumanMessage(content=formatted_prompt)])

    try:
        parsed_data = json.loads(extract_json_text(response.content))
        new_questions = parsed_data.get("questions", [])
        context.context_confidence = float(parsed_data.get("context_confidence", 0.0))
        
        # Extract dimension scores
        dim_scores = parsed_data.get("dimension_scores", {})
        if dim_scores:
            context.dimension_scores = {
                "business_objective": float(dim_scores.get("business_objective", 0)),
                "stakeholders": float(dim_scores.get("stakeholders", 0)),
                "technical_constraints": float(dim_scores.get("technical_constraints", 0)),
                "integration_points": float(dim_scores.get("integration_points", 0)),
                "security_requirements": float(dim_scores.get("security_requirements", 0)),
                "timeline_budget": float(dim_scores.get("timeline_budget", 0)),
                "slas": float(dim_scores.get("slas", 0)),
            }

        # Only add truly new questions (dedup by question text)
        existing_texts = {q.get("question", "") for q in context.questions}
        unique_new = [q for q in new_questions if q.get("question", "") not in existing_texts]
        context.questions.extend(unique_new[:3])  # Max 3 new per round

    except Exception as e:
        print(f"[Question Agent] Error parsing JSON: {e}\nContent was: {response.content}")
        # Force progression if parsing fails so it doesn't get stuck forever
        # But if it fails, maybe we just ask a default question
        context.context_confidence = 1.0
        if context.question_rounds == 0:
            context.questions.append({
                "category": "TECHNICAL",
                "question": "Pode fornecer mais detalhes arquitetónicos sobre o projeto?",
                "rationale": "Fallback due to parsing error."
            })
            context.context_confidence = 0.0 # Force human answer

    context.question_rounds += 1

    # Display confidence panel after EVERY round
    display_confidence_panel(
        round_num=context.question_rounds,
        max_rounds=config.MAX_QUESTION_ROUNDS,
        confidence=context.context_confidence,
        threshold=config.CONFIDENCE_THRESHOLD,
        dimension_scores=context.dimension_scores,
    )

    return {
        "context": context,
        "current_agent": "question_agent",
    }
