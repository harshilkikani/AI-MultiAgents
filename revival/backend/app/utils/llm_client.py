# Why this exists: single place to call Claude with prompt caching on the
# system prompt. Revival generates N messages per campaign with the SAME
# system prompt, so caching saves real money at scale.
from __future__ import annotations

import os
from typing import Optional

from anthropic import Anthropic

from app.utils.logger import get_logger
from app.utils.settings import get_settings

log = get_logger("llm")

# Default generation model; override via CLAUDE_MODEL env for batch runs.
DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
CLASSIFIER_MODEL = os.getenv("CLAUDE_CLASSIFIER_MODEL", "claude-haiku-4-5-20251001")

_client: Optional[Anthropic] = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.anthropic_api_key and not settings.demo_mode:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Put it in revival/backend/.env "
                "or set DEMO_MODE=true."
            )
        _client = Anthropic(api_key=settings.anthropic_api_key or "demo")
    return _client


def call_claude(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 1200,
    model: Optional[str] = None,
    use_cache: bool = True,
) -> str:
    """Single-shot call with optional prompt caching on the system block.

    When DEMO_MODE is set, this raises — callers in DEMO_MODE must route
    through the deterministic templates in `services/revival_templates.py`
    instead of hitting this path.
    """
    settings = get_settings()
    if settings.demo_mode:
        raise RuntimeError(
            "call_claude() invoked while DEMO_MODE=true — use revival_templates "
            "for deterministic demo output."
        )

    client = _get_client()
    model = model or DEFAULT_MODEL

    # System is a list of content blocks so we can mark the shared prompt as
    # cacheable. Anthropic caches prompts >= 1024 tokens at server side and
    # bills subsequent hits at 10% of normal input price.
    system_blocks: list[dict] = [
        {
            "type": "text",
            "text": system_prompt,
            **({"cache_control": {"type": "ephemeral"}} if use_cache else {}),
        }
    ]

    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_blocks,
        messages=[{"role": "user", "content": user_prompt}],
    )
    parts: list[str] = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)
