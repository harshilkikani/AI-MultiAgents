import os
from typing import Optional

from anthropic import Anthropic

from app.utils.logger import get_logger

log = get_logger("llm")

_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
_DEMO = os.getenv("DEMO_MODE", "false").lower() == "true"

_client: Optional[Anthropic] = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key and not _DEMO:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Put it in backend/.env or set DEMO_MODE=true."
            )
        _client = Anthropic(api_key=api_key) if api_key else Anthropic(api_key="demo")
    return _client


def call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 1200) -> str:
    """Single-shot call to Claude. Returns the raw text content."""
    if _DEMO:
        from app.utils.demo_responses import demo_response_for
        return demo_response_for(system_prompt, user_prompt)

    client = _get_client()
    msg = client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # Concatenate all text blocks
    parts = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)
