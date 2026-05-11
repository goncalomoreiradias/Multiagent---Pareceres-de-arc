import os
import json
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from config import config

def run_writing(state: GraphState) -> dict:
    """Drafts the Parecer de Arquitetura in pt-PT."""
    print("[Architect Writer] Drafting the Parecer de Arquitetura...")
    context = state["context"]
    
    prompt_path = os.path.join(config.PROMPTS_DIR, "writer.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    formatted_prompt = prompt_template.replace("{project_name}", context.project_name)\
                                      .replace("{request_type}", str(context.request_type))\
                                      .replace("{business_requirements}", json.dumps(context.business_requirements, ensure_ascii=False))\
                                      .replace("{architectural_reasoning}", json.dumps(context.architectural_reasoning, ensure_ascii=False))\
                                      .replace("{trade_offs}", json.dumps(context.trade_offs, ensure_ascii=False))
                                      
    llm = config.get_llm()
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    context.draft_report_md = response.content.strip()
    
    return {
        "context": context,
        "current_agent": "architect_writer"
    }
