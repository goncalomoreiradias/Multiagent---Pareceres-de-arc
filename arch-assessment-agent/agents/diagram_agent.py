import os
import json
from datetime import datetime
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.response_parser import extract_json_text
from config import config

def run_diagram_gen(state: GraphState) -> dict:
    """Generates Mermaid diagrams and ArchiMate draw.io XML."""
    print("[Diagram Agent] Generating architectural diagrams (Mermaid + ArchiMate)...")
    context = state["context"]
    
    # Ensure assessment_id exists
    if not context.assessment_id:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        context.assessment_id = f"ASS-{timestamp}"
    
    prompt_path = os.path.join(config.PROMPTS_DIR, "diagrams.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    formatted_prompt = prompt_template.replace("{project_name}", context.project_name)\
                                      .replace("{architectural_reasoning}", json.dumps(context.architectural_reasoning))\
                                      .replace("{impacted_systems}", json.dumps(context.impacted_systems))\
                                      .replace("{business_requirements}", json.dumps(context.business_requirements, ensure_ascii=False))\
                                      .replace("{technical_constraints}", json.dumps(context.technical_constraints, ensure_ascii=False))
                                      
    llm = config.get_llm("gemini_pro")
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    try:
        parsed_data = json.loads(extract_json_text(response.content))
        
        context.diagrams = {
            "sequence_diagram": parsed_data.get("sequence_diagram", ""),
            "flowchart": parsed_data.get("flowchart", ""),
            "capabilities_drawio": parsed_data.get("capabilities_drawio", "")
        }
        
        # Save the .drawio file to disk
        drawio_content = context.diagrams.get("capabilities_drawio", "")
        if drawio_content and drawio_content.strip().startswith("<mxfile"):
            diagrams_dir = os.path.join(config.OUTPUT_DIR, "diagrams")
            os.makedirs(diagrams_dir, exist_ok=True)
            drawio_path = os.path.join(diagrams_dir, f"{context.assessment_id}_capabilities.drawio")
            with open(drawio_path, "w", encoding="utf-8") as f:
                f.write(drawio_content)
            print(f"[Diagram Agent] ArchiMate diagram saved to: {drawio_path}")
        else:
            print("[Diagram Agent] Warning: capabilities_drawio is empty or invalid XML, skipping .drawio save.")
        
    except Exception as e:
        print(f"[Diagram Agent] Error parsing JSON: {e}")
        
    return {
        "context": context,
        "current_agent": "diagram_agent"
    }
