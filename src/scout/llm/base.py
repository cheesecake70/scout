from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod

from ..models import Paper

log = logging.getLogger(__name__)


class LLM(ABC):
    name = "base"

    @abstractmethod
    def complete(self, system: str, user: str, *, max_tokens: int = 600) -> str: ...

    # ---- tasks ------------------------------------------------------
    def gap_queries(self, gap_text: str) -> list[str]:
        sys_ = ("You turn a researcher's notes about what they did NOT understand into literature search queries. "
                "Reply with a JSON list of 2-3 short search queries (4-10 words each), most specific first. No prose.")
        out = self.complete(sys_, f"Gaps from recent reading:\n\n{gap_text}", max_tokens=200)
        return _json_list(out)[:3]

    def explain(self, paper: Paper, profile: str, gap_notes, lane: str) -> tuple[str, str]:
        gaps = "\n".join(f"- {n.title}: {n.gaps[:300]}" for n in gap_notes) or "(none yet)"
        sys_ = ("You write two short fields for a daily paper recommendation. Be concrete and specific to this reader. "
                "No hype, no 'groundbreaking'. Reply as JSON: {\"why\": \"2-3 sentences\", \"payoff\": \"1-2 sentences\"}.\n"
                "'why' ties the paper to the reader's profile and, if relevant, to a recent gap they wrote down. "
                "'payoff' says what they will concretely understand or be able to try after reading.")
        user = (f"READER PROFILE:\n{profile[:2500]}\n\nREADER'S RECENT GAPS:\n{gaps}\n\n"
                f"LANE: {lane} ({paper.source_reason})\n\nPAPER:\nTitle: {paper.title}\nAuthors: {', '.join(paper.authors[:5])}\n"
                f"Venue: {paper.venue} {paper.published or ''}\nAbstract: {paper.abstract[:2500]}")
        out = self.complete(sys_, user, max_tokens=400)
        d = _json_obj(out)
        return (d.get("why", "").strip(), d.get("payoff", "").strip())

    def choose_essential(self, papers: list[Paper], profile: str) -> str | None:
        sys_ = ("Pick the single most foundational paper for this reader from the list: one that later work in their "
                "area keeps building on and that they'd be embarrassed not to have read. Reply with just its id.")
        listing = "\n".join(f"{p.id} | {p.title} | {p.venue} {p.published.year if p.published else ''} | cites={p.citation_count}"
                            for p in papers)
        out = self.complete(sys_, f"READER:\n{profile[:1500]}\n\nCANDIDATES:\n{listing}", max_tokens=60).strip()
        ids = {p.id for p in papers}
        for tok in re.split(r"[\s,`\"']+", out):
            if tok in ids:
                return tok
        return None


def _json_list(text: str) -> list[str]:
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return [l.strip("-• ").strip() for l in text.splitlines() if l.strip()][:3]
    try:
        v = json.loads(m.group(0))
        return [str(x) for x in v if str(x).strip()]
    except ValueError:
        return []


def _json_obj(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except ValueError:
        return {}
