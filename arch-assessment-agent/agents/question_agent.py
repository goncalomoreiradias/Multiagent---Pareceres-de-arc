import os
import sys
import json
import re
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.response_parser import extract_json_text
from config import config

# Dimension definitions for scoring logic
DIMENSIONS = [
    ("business_objective", "Objetivo de negócio definido", 20),
    ("stakeholders", "Stakeholders identificados", 10),
    ("technical_constraints", "Restrições técnicas conhecidas", 20),
    ("integration_points", "Pontos de integração mapeados", 15),
    ("security_requirements", "Requisitos de segurança definidos", 15),
    ("timeline_budget", "Prazo e orçamento conhecidos", 10),
    ("slas", "SLAs definidos", 10),
]

def display_confidence_panel(round_num: int, max_rounds: int, confidence: float, threshold: float, scores: dict):
    """Simple text fallback for confidence monitoring."""
    pass

def run_question_loop(state: GraphState) -> dict:
    """Generates questions to clarify the context."""
    context = state["context"]
    round_num = context.question_rounds + 1

    # Check if the user explicitly asked to advance
    last_input = context.raw_input.split("\n\n")[-1].lower()
    
    # Extract and normalize the user's response to check for skip commands
    import unicodedata
    def clean_and_normalize(text):
        normalized = "".join(
            c for c in unicodedata.normalize('NFD', text.lower())
            if unicodedata.category(c) != 'Mn'
        )
        return normalized.strip("] \n\r\t.")

    user_ans = ""
    if "[resposta:" in last_input:
        parts = last_input.split("[resposta:")
        if len(parts) > 1:
            user_ans = clean_and_normalize(parts[-1])
    elif "user answer:" in last_input:
        parts = last_input.split("user answer:")
        if len(parts) > 1:
            user_ans = clean_and_normalize(parts[-1])
    else:
        user_ans = clean_and_normalize(last_input)

    if user_ans in ["avancar", "avanca", "advance", "pular", "skip", "next"]:
        context.context_confidence = 1.0
        return {"context": context, "current_agent": "question_agent"}


    prompt_path = os.path.join(config.PROMPTS_DIR, "questions.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Format current scores for the prompt
    scores_str = json.dumps(context.dimension_scores, indent=2)
    
    # Build previous questions string
    prev_qs = "\n".join([f"- {q.get('question')}" for q in context.questions])
    
    # Safely format the prompt using replace to avoid KeyError from .format()
    formatted_prompt = prompt_template.replace("{request_type}", str(context.request_type))\
                                      .replace("{project_name}", context.project_name)\
                                      .replace("{brief_description}", context.brief_description)\
                                      .replace("{impacted_systems}", json.dumps(context.impacted_systems, ensure_ascii=False))\
                                      .replace("{raw_input}", context.raw_input)\
                                      .replace("{previous_questions}", prev_qs)\
                                      .replace("{current_scores}", scores_str)

    llm = config.get_llm()
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    try:
        data = json.loads(extract_json_text(response.content))
        
        # Update context
        context.questions.extend(data.get("questions", []))
        context.question_rounds = round_num
        
        # Update scores
        new_scores = data.get("dimension_scores", {})
        context.dimension_scores.update(new_scores)
        
        # Calculate new total confidence
        total_score = sum(context.dimension_scores.values())
        max_possible = sum(d[2] for d in DIMENSIONS)
        context.context_confidence = total_score / max_possible if max_possible > 0 else 0.0

        # Display progress
        display_confidence_panel(
            round_num, 
            config.MAX_QUESTION_ROUNDS, 
            context.context_confidence, 
            config.CONFIDENCE_THRESHOLD,
            context.dimension_scores
        )

    except Exception:
        # Safeguard: if parsing fails, we don't block, just assume same confidence
        context.question_rounds = round_num

    return {"context": context, "current_agent": "question_agent"}
