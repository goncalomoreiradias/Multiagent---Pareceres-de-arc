"""Extended test: validates response_parser handles Gemini 3.x list content format."""
import json
from tools.response_parser import extract_text, extract_json_text

# Simulate what Gemini 3.x actually returns
gemini_list_response = [
    {"type": "text", "text": '{\n  "status": "ok",\n  "result": 42\n}', "extras": {"signature": "abc123"}}
]

# Simulate plain string (older models)
plain_response = '{"status": "ok", "result": 42}'

# With markdown fence (common LLM output)
fenced_response = "Here is the JSON:\n```json\n{\"status\": \"ok\", \"result\": 42}\n```"

print("=== extract_text ===")
print("List input:", extract_text(gemini_list_response))
print("Plain input:", extract_text(plain_response))

print("\n=== extract_json_text ===")
for label, content in [("List", gemini_list_response), ("Plain", plain_response), ("Fenced", fenced_response)]:
    raw = extract_json_text(content)
    parsed = json.loads(raw)
    print(f"{label}: {parsed}")

print("\nAll tests passed!")
