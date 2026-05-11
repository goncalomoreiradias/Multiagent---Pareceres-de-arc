import os
import json
import difflib
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
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
    
    # Very simple keyword matching for MVP
    matched_systems = []
    for app in portfolio:
        name_lower = app["name"].lower()
        if name_lower in text_to_search or name_lower.replace("sd", "") in text_to_search:
            matched_systems.append(app)
            
    # If no matches found via keyword, return all for the LLM to figure out, 
    # or just return the full portfolio in MVP since it's small.
    if not matched_systems:
        return json.dumps(portfolio, indent=2)
        
    return json.dumps(matched_systems, indent=2)

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
                                      
    llm = config.get_llm()
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    try:
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        parsed_data = json.loads(content.strip())
        
        context.impacted_systems = parsed_data.get("impacted_systems", [])
        context.integration_points = parsed_data.get("integration_points", {})
        
    except Exception as e:
        print(f"[Impact Agent] Error parsing JSON: {e}")
        state["error"] = f"Impact JSON parsing failed: {e}"

    return {
        "context": context,
        "current_agent": "impact_agent"
    }
