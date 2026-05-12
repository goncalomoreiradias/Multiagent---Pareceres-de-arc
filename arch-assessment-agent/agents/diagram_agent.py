import os
import json
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.response_parser import extract_json_text
from config import config

def run_diagram_gen(state: GraphState) -> dict:
    """Generates Mermaid diagrams."""
    print("[Diagram Agent] Generating architectural diagrams...")
    context = state["context"]
    
    prompt_path = os.path.join(config.PROMPTS_DIR, "diagrams.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    formatted_prompt = prompt_template.replace("{project_name}", context.project_name)\
                                      .replace("{architectural_reasoning}", json.dumps(context.architectural_reasoning))\
                                      .replace("{impacted_systems}", json.dumps(context.impacted_systems))
                                      
    llm = config.get_llm("gemini_pro")
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    try:
        parsed_data = json.loads(extract_json_text(response.content))
        
        context.diagrams = {
            "sequence_diagram": parsed_data.get("sequence_diagram", ""),
            "flowchart": parsed_data.get("flowchart", "")
        }
        
    except Exception as e:
        print(f"[Diagram Agent] Error parsing JSON: {e}")
        
    return {
        "context": context,
        "current_agent": "diagram_agent"
    }
