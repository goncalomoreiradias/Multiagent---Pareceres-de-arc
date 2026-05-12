import json
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.response_parser import extract_json_text
from config import config

def run_context_build(state: GraphState) -> dict:
    """Consolidates all raw input and answers into structured requirements."""
    print("[Context Builder] Consolidating requirements and constraints...")
    context = state["context"]
    
    prompt = f"""
    You are an expert Requirements Analyst. 
    Review the following raw input and Q&A history, and extract structured lists of:
    - Business Requirements
    - Technical Constraints
    - Risks
    - Assumptions
    
    Raw Data:
    {context.raw_input}
    
    Impacted Systems:
    {json.dumps(context.impacted_systems)}
    
    Return the output strictly in this JSON format:
    {{
        "business_requirements": ["Req 1", "Req 2"],
        "technical_constraints": ["Constraint 1"],
        "risks": ["Risk 1"],
        "assumptions": ["Assumption 1"]
    }}
    """
    
    llm = config.get_llm("gemini_flash")
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        parsed_data = json.loads(extract_json_text(response.content))
        
        context.business_requirements = parsed_data.get("business_requirements", [])
        context.technical_constraints = parsed_data.get("technical_constraints", [])
        context.risks = parsed_data.get("risks", [])
        context.assumptions = parsed_data.get("assumptions", [])
        
    except Exception as e:
        print(f"[Context Builder] Error parsing JSON: {e}")
        
    return {
        "context": context,
        "current_agent": "context_builder"
    }
