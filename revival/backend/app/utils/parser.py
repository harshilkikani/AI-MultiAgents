# Why this exists: Claude sometimes wraps JSON in prose or code fences.
# This extractor is permissive — works on raw JSON, fenced JSON, or JSON
# surrounded by filler text.
import json
import re
from typing import Any


def _parse_balanced(text: str, open_ch: str, close_ch: str) -> Any | None:
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
    if not text:
        raise ValueError("Empty LLM response")

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        out = _parse_balanced(candidate, open_ch, close_ch)
        if out is not None:
            return out

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}")
