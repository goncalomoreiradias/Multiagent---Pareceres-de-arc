import os
import json
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.response_parser import extract_json_text
from config import config

def run_reasoning(state: GraphState) -> dict:
    """The core thinking engine (TOGAF ADM based)."""
    context = state["context"]
    
    prompt_path = os.path.join(config.PROMPTS_DIR, "reasoner.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    formatted_prompt = prompt_template.replace("{project_name}", context.project_name)\
                                      .replace("{request_type}", str(context.request_type))\
                                      .replace("{business_requirements}", json.dumps(context.business_requirements))\
                                      .replace("{technical_constraints}", json.dumps(context.technical_constraints))\
                                      .replace("{risks}", json.dumps(context.risks))\
                                      .replace("{assumptions}", json.dumps(context.assumptions))\
                                      .replace("{impacted_systems}", json.dumps(context.impacted_systems))
                                      
    llm = config.get_llm("gemini_pro") # Standard reasoning model
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    try:
        parsed_data = json.loads(extract_json_text(response.content))
        
        context.architectural_reasoning = parsed_data.get("architectural_reasoning", {})
        context.candidate_architectures = parsed_data.get("candidate_architectures", [])
        context.trade_offs = parsed_data.get("trade_offs", {})
        
    except Exception as e:
        state["error"] = f"Reasoning failed: {e}"
        
    return {
        "context": context,
        "current_agent": "architect_reasoner"
    }
