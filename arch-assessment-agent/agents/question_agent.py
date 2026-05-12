import os
import json
import re
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.response_parser import extract_json_text
from config import config


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

    return {
        "context": context,
        "current_agent": "question_agent",
    }
