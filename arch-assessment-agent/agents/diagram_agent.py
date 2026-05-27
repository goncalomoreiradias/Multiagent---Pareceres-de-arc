import os
import json
from datetime import datetime
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.response_parser import extract_json_text
from config import config

def run_diagram_gen(state: GraphState) -> dict:
    """Generates or updates Mermaid diagrams and ArchiMate draw.io XML."""
    context = state["context"]
    
    # Ensure assessment_id exists
    if not context.assessment_id:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        context.assessment_id = f"ASS-{timestamp}"
    
    # Check if we should run in update/reshape mode
    user_feedback = state.get("user_feedback", "")
    if isinstance(user_feedback, list):
        user_feedback = " ".join(str(v) for v in user_feedback)
    user_feedback = str(user_feedback or "").strip()
    
    is_update = user_feedback != "" and context.diagrams and any(context.diagrams.values())
    
    if is_update:
        prompt_path = os.path.join(config.PROMPTS_DIR, "diagrams_update.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
            
        formatted_prompt = prompt_template.replace("{project_name}", context.project_name)\
                                          .replace("{impacted_systems}", json.dumps(context.impacted_systems))\
                                          .replace("{business_requirements}", json.dumps(context.business_requirements, ensure_ascii=False))\
                                          .replace("{technical_constraints}", json.dumps(context.technical_constraints, ensure_ascii=False))\
                                          .replace("{user_feedback}", user_feedback)\
                                          .replace("{draft_report_md}", context.draft_report_md)\
                                          .replace("{current_sequence}", context.diagrams.get("sequence_diagram", ""))\
                                          .replace("{current_flowchart}", context.diagrams.get("flowchart", ""))\
                                          .replace("{current_capabilities_drawio}", context.diagrams.get("capabilities_drawio", ""))
    else:
        prompt_path = os.path.join(config.PROMPTS_DIR, "diagrams.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
            
        formatted_prompt = prompt_template.replace("{project_name}", context.project_name)\
                                          .replace("{architectural_reasoning}", json.dumps(context.architectural_reasoning))\
                                          .replace("{impacted_systems}", json.dumps(context.impacted_systems))\
                                          .replace("{business_requirements}", json.dumps(context.business_requirements, ensure_ascii=False))\
                                          .replace("{technical_constraints}", json.dumps(context.technical_constraints, ensure_ascii=False))
                                          
        if hasattr(context, "selected_diagrams") and context.selected_diagrams:
            selected_str = ", ".join(context.selected_diagrams)
            diagrams_instruction = (
                f"\n\nCRITICAL: The user has selected only the following diagram types to generate: {selected_str}.\n"
                "Generate ONLY the requested diagrams. For any diagram type that is NOT selected, you MUST return an empty string (\"\") as its value in the JSON response (both for the diagram code/xml and its corresponding explanation field)."
            )
            formatted_prompt += diagrams_instruction
                                          
    llm = config.get_llm("gemini_pro")
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    try:
        parsed_data = json.loads(extract_json_text(response.content))
        
        context.diagrams = {
            "sequence_diagram": parsed_data.get("sequence_diagram", ""),
            "sequence_explanation": parsed_data.get("sequence_explanation", ""),
            "flowchart": parsed_data.get("flowchart", ""),
            "flowchart_explanation": parsed_data.get("flowchart_explanation", ""),
            "capabilities_drawio": parsed_data.get("capabilities_drawio", ""),
            "capabilities_explanation": parsed_data.get("capabilities_explanation", "")
        }
        
        # Save the .drawio file to disk
        drawio_content = context.diagrams.get("capabilities_drawio", "")
        if drawio_content and drawio_content.strip().startswith("<mxfile"):
            diagrams_dir = os.path.join(config.OUTPUT_DIR, "diagrams")
            os.makedirs(diagrams_dir, exist_ok=True)
            drawio_path = os.path.join(diagrams_dir, f"{context.assessment_id}_capabilities.drawio")
            with open(drawio_path, "w", encoding="utf-8") as f:
                f.write(drawio_content)
        
        # Inject diagrams into draft_report_md
        from tools.markdown_exporter import inject_diagrams
        context.draft_report_md = inject_diagrams(context.draft_report_md, context.diagrams, context.assessment_id)
        
    except Exception as e:
        # Log the error to the state so we can see it in the UI if needed
        state["error"] = f"Diagram Agent JSON error: {str(e)}"
        pass
        
    return {
        "context": context,
        "current_agent": "diagram_agent"
    }

