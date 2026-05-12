"""Shared utility to safely extract text content from LLM responses.

Gemini 3.x returns response.content as either:
  - A plain string (older models / simple responses)
  - A list of content blocks: [{'type': 'text', 'text': '...'}, ...]

This helper normalises both formats.
"""
import re


def extract_text(response_content) -> str:
    """Extract plain text from an LLM response content (str or list of blocks)."""
    if isinstance(response_content, str):
        return response_content
    if isinstance(response_content, list):
        parts = []
        for block in response_content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(response_content)


def extract_json_text(response_content) -> str:
    """Extract text and strip markdown code fences, returning raw JSON string."""
    text = extract_text(response_content)
    # Try to pull out the first {...} or [...] block robustly
    match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if match:
        return match.group(0)
    # Fallback: strip code fences manually
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return text.strip()
