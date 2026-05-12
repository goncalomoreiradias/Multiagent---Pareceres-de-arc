import os
import json
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.markdown_exporter import inject_diagrams
from tools.response_parser import extract_json_text
from config import config

def run_review(state: GraphState) -> dict:
    """Acts as the Architecture Board, reviewing the draft."""
    print("[Reviewer Agent] Reviewing the draft assessment...")
    context = state["context"]
    
    # First, inject diagrams into the draft report for review
    full_draft = inject_diagrams(context.draft_report_md, context.diagrams)
    
    prompt_path = os.path.join(config.PROMPTS_DIR, "reviewer.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    formatted_prompt = prompt_template.replace("{draft_report_md}", full_draft)
                                      
    llm = config.get_llm("gemini_pro")
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    try:
        parsed_data = json.loads(extract_json_text(response.content))
        
        context.reviewer_feedback = parsed_data.get("reviewer_feedback", [])
        
    except Exception as e:
        print(f"[Reviewer Agent] Error parsing JSON: {e}")
        
    # Overwrite draft with the diagram-injected version
    context.draft_report_md = full_draft
    
    return {
        "context": context,
        "current_agent": "reviewer_agent"
    }
