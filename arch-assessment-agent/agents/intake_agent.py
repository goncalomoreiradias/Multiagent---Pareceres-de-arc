import os
import json
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from config import config

def run_intake(state: GraphState) -> dict:
    """Classifies the architectural request and extracts initial info."""
    print("[Intake Agent] Analyzing request...")
    
    # We retrieve the raw input from the state context
    context = state["context"]
    raw_input = context.raw_input
    
    # Load prompt
    prompt_path = os.path.join(config.PROMPTS_DIR, "intake.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    formatted_prompt = prompt_template.replace("{raw_input}", raw_input)
    
    # Get LLM and invoke
    llm = config.get_llm()
    # We ask the LLM to output JSON, LangChain can enforce this via structure or we just parse it.
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    # Naive JSON extraction (in production, use structured outputs or json parser)
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        parsed_data = json.loads(content.strip())
        
        # Update context
        context.request_type = parsed_data.get("request_type")
        context.classification_confidence = float(parsed_data.get("classification_confidence", 0.0))
        context.project_name = parsed_data.get("project_name", "Unknown Project")
        context.requestor = parsed_data.get("requestor", "Unknown Requestor")
        context.urgency = parsed_data.get("urgency", "Normal")
        context.brief_description = parsed_data.get("brief_description", "")
        
    except Exception as e:
        print(f"[Intake Agent] Error parsing JSON: {e}")
        state["error"] = f"Intake JSON parsing failed: {e}"
        
    # Return ONLY the partial state updates (LangGraph will merge them)
    # The 'context' object is mutable so technically we mutated it, but we return it anyway
    return {
        "context": context,
        "current_agent": "intake_agent",
        "error": state.get("error")
    }
