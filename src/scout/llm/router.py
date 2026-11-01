"""Pick the first provider in settings.llm.provider_order whose key is set and SDK imports.
Every task degrades to None (caller falls back to abstract snippets) if all providers fail."""
from __future__ import annotations

import logging
import os

from ..config import Settings
from .base import LLM

log = logging.getLogger(__name__)
KEYS = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY"}
DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "gemini": "gemini-2.5-flash", "groq": "llama-3.3-70b-versatile"}


class Resilient(LLM):
    """Wraps a provider chain: try each in order per call."""
    name = "chain"

    def __init__(self, chain: list[LLM]):
        self.chain = chain

    def complete(self, system: str, user: str, *, max_tokens: int = 600) -> str:
        for llm in self.chain:
            try:
                return llm.complete(system, user, max_tokens=max_tokens)
            except Exception as e:  # noqa: BLE001
                log.warning("%s failed: %s", llm.name, e)
        return ""


def get_llm(settings: Settings) -> LLM | None:
    chain: list[LLM] = []
    for name in settings.llm.provider_order:
        if not os.environ.get(KEYS.get(name, "")):
            continue
        model = settings.llm.models.get(name) or DEFAULT_MODELS.get(name, "")
        try:
            if name == "anthropic":
                from .anthropic import Anthropic
                chain.append(Anthropic(model))
            elif name == "gemini":
                from .gemini import Gemini
                chain.append(Gemini(model))
            elif name == "groq":
                from .groq import Groq
                chain.append(Groq(model))
        except Exception as e:  # noqa: BLE001
            log.warning("could not init %s: %s", name, e)
    if not chain:
        log.info("no LLM provider configured; picks will use abstract snippets")
        return None
    log.info("LLM chain: %s", " > ".join(l.name for l in chain))
    return Resilient(chain)
