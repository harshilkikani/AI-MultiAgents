import json
import re
from typing import Any


def _parse_balanced(text: str, open_ch: str, close_ch: str) -> Any | None:
    """Find the first balanced bracket block and try to json-parse it."""
    start = text.find(open_ch)
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def extract_json(text: str) -> Any:
    """Pull the first valid JSON object/array out of an LLM response.

    Handles three shapes:
    1. Raw JSON — `{...}` or `[...]`
    2. Fenced JSON — ```json\n{...}\n```
    3. JSON wrapped in prose
    """
    if not text:
        raise ValueError("Empty LLM response")

    # Strip code fences first (greedy so nested braces inside are preserved)
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text

    # Try direct parse
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Balanced-bracket scan for an object, then array
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        out = _parse_balanced(candidate, open_ch, close_ch)
        if out is not None:
            return out

    # Final fallback: raise a clear error
    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")
