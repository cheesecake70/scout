from __future__ import annotations

import os

from .base import LLM


class Gemini(LLM):
    name = "gemini"

    def __init__(self, model: str):
        from google import genai  # type: ignore
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.model = model

    def complete(self, system: str, user: str, *, max_tokens: int = 600) -> str:
        from google.genai import types  # type: ignore
        r = self.client.models.generate_content(
            model=self.model, contents=user,
            config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens))
        return r.text or ""
