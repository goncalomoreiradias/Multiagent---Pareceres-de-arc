import os
import json
from datetime import datetime
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.response_parser import extract_text
from config import config

def run_writing(state: GraphState) -> dict:
    """Drafts the Parecer de Arquitetura in pt-PT."""
    context = state["context"]
    
    # Generate assessment_id if not already set
    if not context.assessment_id:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        context.assessment_id = f"ASS-{timestamp}"
    
    prompt_path = os.path.join(config.PROMPTS_DIR, "writer.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    formatted_prompt = prompt_template.replace("{project_name}", context.project_name)\
                                      .replace("{assessment_id}", context.assessment_id)\
                                      .replace("{request_type}", str(context.request_type))\
                                      .replace("{business_requirements}", json.dumps(context.business_requirements, ensure_ascii=False))\
                                      .replace("{technical_constraints}", json.dumps(context.technical_constraints, ensure_ascii=False))\
                                      .replace("{architectural_reasoning}", json.dumps(context.architectural_reasoning, ensure_ascii=False))\
                                      .replace("{trade_offs}", json.dumps(context.trade_offs, ensure_ascii=False))\
                                      .replace("{impacted_systems}", json.dumps(context.impacted_systems, ensure_ascii=False))\
                                      .replace("{risks}", json.dumps(context.risks, ensure_ascii=False))\
                                      .replace("{assumptions}", json.dumps(context.assumptions, ensure_ascii=False))\
                                      .replace("{diagrams_context}", json.dumps(context.diagrams, ensure_ascii=False))
                                      
    llm = config.get_llm("gemini_pro")
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    context.draft_report_md = extract_text(response.content).strip()
    
    return {
        "context": context,
        "current_agent": "architect_writer"
    }
