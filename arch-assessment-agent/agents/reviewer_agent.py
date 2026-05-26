import os
import json
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.response_parser import extract_json_text
from config import config

def run_review(state: GraphState) -> dict:
    """Acts as the Architecture Board, reviewing the draft."""
    context = state["context"]
    
    prompt_path = os.path.join(config.PROMPTS_DIR, "reviewer.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    formatted_prompt = prompt_template.replace("{draft_report_md}", context.draft_report_md)
                                      
    llm = config.get_llm("gemini_pro")
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    try:
        parsed_data = json.loads(extract_json_text(response.content))
        
        context.reviewer_approved = parsed_data.get("is_approved", False)
        context.reviewer_feedback = parsed_data.get("reviewer_feedback", [])
        
    except Exception:
        context.reviewer_approved = False
        pass
        
    context.reviewer_run_count += 1
    
    return {
        "context": context,
        "current_agent": "reviewer_agent"
    }
