from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Lane = Literal["niche", "neighbourhood", "field", "essential", "want", "own"]
Depth = Literal["deep", "skim"]


def normalise_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


class Paper(BaseModel):
    id: str                                  # canonical: arXiv id without version, else DOI, else s2:<id>
    title: str
    abstract: str = ""
    authors: list[str] = []
    published: date | None = None
    url: str = ""
    pdf_url: str = ""
    venue: str = ""
    arxiv_id: str | None = None
    doi: str | None = None
    s2_id: str | None = None
    citation_count: int | None = None
    influential_citation_count: int | None = None
    hf_upvotes: int | None = None
    source_lanes: set[str] = Field(default_factory=set)   # which lanes proposed it
    source_reason: str = ""                                # e.g. "cites <id>", "gap query: ..."

    @property
    def norm_title(self) -> str:
        return normalise_title(self.title)

    def text(self) -> str:
        return f"{self.title}\n\n{self.abstract}"


class Pick(BaseModel):
    paper: Paper
    lane: Lane
    depth: Depth
    score: float
    why: str = ""
    payoff: str = ""
    led_from: list[str] = []      # note ids whose gaps produced this pick


class Today(BaseModel):
    date: date
    picks: list[Pick]
    generated_at: datetime
    gap_queries: list[str] = []


class WantItem(BaseModel):
    id: str
    title: str = ""
    url: str = ""
    why: str = ""
    by_when: date | None = None
    added: date
    served: bool = False
