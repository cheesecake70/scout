from __future__ import annotations

import os

from .base import LLM


class Anthropic(LLM):
    name = "anthropic"

    def __init__(self, model: str):
        import anthropic  # type: ignore
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model

    def complete(self, system: str, user: str, *, max_tokens: int = 600) -> str:
        r = self.client.messages.create(model=self.model, max_tokens=max_tokens, system=system,
                                        messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
