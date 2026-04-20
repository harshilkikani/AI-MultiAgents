import os
import time
from pathlib import Path
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.utils.llm_client import call_claude
from app.utils.parser import extract_json
from app.utils.logger import get_logger

T = TypeVar("T", bound=BaseModel)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / name
    return path.read_text(encoding="utf-8")


class BaseAgent:
    """Shared wiring: loads a system prompt, calls Claude, parses JSON, validates."""

    name: str = "agent"
    prompt_file: str = ""
    output_model: Type[BaseModel] = BaseModel

    def __init__(self):
        self.log = get_logger(f"agent.{self.name}")
        self.system_prompt = _load_prompt(self.prompt_file) if self.prompt_file else ""

    def run(self, user_prompt: str) -> BaseModel:
        self.log.info(f"{self.name} :: started")
        self.log.info(f"{self.name} :: input -> {user_prompt[:200]}")
        started = time.time()
        raw = call_claude(self.system_prompt, user_prompt)
        try:
            data = extract_json(raw)
            out = self.output_model.model_validate(data)
        except (ValueError, ValidationError) as first_err:
            self.log.warning(f"{self.name} :: first attempt failed, retrying: {first_err}")
            retry_prompt = (
                f"{user_prompt}\n\n"
                f"Your previous response could not be parsed. "
                f"Return ONLY a valid JSON object matching the schema. "
                f"No markdown fences, no prose. Error was: {first_err}"
            )
            raw = call_claude(self.system_prompt, retry_prompt)
            try:
                data = extract_json(raw)
                out = self.output_model.model_validate(data)
            except (ValueError, ValidationError) as e:
                self.log.error(f"{self.name} :: retry also failed: {e}")
                self.log.error(f"{self.name} :: raw -> {raw[:400]}")
                raise
        dur = int((time.time() - started) * 1000)
        self.log.info(f"{self.name} :: ok in {dur}ms")
        return out

    def run_text(self, user_prompt: str) -> str:
        """For the manager agent which returns prose, not JSON."""
        self.log.info(f"{self.name} :: started (text)")
        started = time.time()
        raw = call_claude(self.system_prompt, user_prompt, max_tokens=500)
        dur = int((time.time() - started) * 1000)
        self.log.info(f"{self.name} :: ok in {dur}ms")
        return raw.strip()
