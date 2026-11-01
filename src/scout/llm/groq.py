from __future__ import annotations

import os

from .base import LLM


class Groq(LLM):
    name = "groq"

    def __init__(self, model: str):
        from groq import Groq as _Groq  # type: ignore
        self.client = _Groq(api_key=os.environ["GROQ_API_KEY"])
        self.model = model

    def complete(self, system: str, user: str, *, max_tokens: int = 600) -> str:
        r = self.client.chat.completions.create(
            model=self.model, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return r.choices[0].message.content or ""
