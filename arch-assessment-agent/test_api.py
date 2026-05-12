"""Quick test to validate API connectivity and model identifiers."""
from config import config
from langchain_core.messages import HumanMessage

def test_model(name):
    print(f"\n--- Testing: {name} ---")
    try:
        llm = config.get_llm(name)
        resp = llm.invoke([HumanMessage(content='Respond ONLY with valid JSON: {"status": "ok"}')])
        content = resp.content
        print(f"SUCCESS. Response snippet: {content[:200]}")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

test_model("gemini_pro")
test_model("gemini_flash")
