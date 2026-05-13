import os
import json
import difflib
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.response_parser import extract_json_text
from config import config

def fuzzy_match_portfolio(raw_input: str, brief_description: str) -> str:
    """MVP matching: find portfolio items mentioned in the text."""
    portfolio_path = os.path.join(config.DATA_DIR, "application_portfolio.json")
    try:
        with open(portfolio_path, "r", encoding="utf-8") as f:
            portfolio = json.load(f)
    except Exception:
        return "[]"
        
    text_to_search = f"{raw_input} {brief_description}".lower()
    
    # Improved matching for the new portfolio structure
    matched_systems = []
    for app in portfolio:
        sigla = str(app.get("SIGLA", "")).lower()
        nome = str(app.get("NOME APLICAÇÃO", "")).lower()
        
        # Match by Sigla (exact or in text) or Name
        if (sigla and sigla in text_to_search) or (nome and nome in text_to_search):
            matched_systems.append(app)
            
    # If too many matches or none, we limit to avoid blowing up the LLM context
    # In a real scenario, we'd use a vector DB, but for now we take the top 20 or all if small
    if not matched_systems:
        return json.dumps(portfolio[:20], indent=2) # Return a sample if nothing matches
        
    return json.dumps(matched_systems[:30], indent=2)

def run_impact_analysis(state: GraphState) -> dict:
    """Identifies impacted systems using the portfolio."""
    print("[Impact Agent] Analyzing portfolio impact...")
    context = state["context"]
    
    prompt_path = os.path.join(config.PROMPTS_DIR, "impact.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
        
    relevant_portfolio = fuzzy_match_portfolio(context.raw_input, context.brief_description)
        
    formatted_prompt = prompt_template.replace("{raw_input}", context.raw_input)\
                                      .replace("{brief_description}", context.brief_description)\
                                      .replace("{portfolio_json}", relevant_portfolio)
                                      
    llm = config.get_llm("gemini_pro")
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    try:
        parsed_data = json.loads(extract_json_text(response.content))
        
        context.impacted_systems = parsed_data.get("impacted_systems", [])
        context.integration_points = parsed_data.get("integration_points", {})
        
    except Exception as e:
        print(f"[Impact Agent] Error parsing JSON: {e}")
        state["error"] = f"Impact JSON parsing failed: {e}"

    return {
        "context": context,
        "current_agent": "impact_agent"
    }
