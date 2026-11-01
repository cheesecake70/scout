from __future__ import annotations

import logging
from datetime import date

from ..models import Paper
from .http import get
from .ids import strip_arxiv_version

log = logging.getLogger(__name__)
API = "https://huggingface.co/api/daily_papers"


def trending(*, limit: int = 40) -> list[Paper]:
    d = get(API, params={"limit": limit})
    out: list[Paper] = []
    for item in d or []:
        p = item.get("paper") or {}
        aid = strip_arxiv_version(p.get("id", ""))
        if not aid:
            continue
        pub = None
        if p.get("publishedAt"):
            try:
                pub = date.fromisoformat(p["publishedAt"][:10])
            except ValueError:
                pass
        out.append(Paper(
            id=aid, arxiv_id=aid, title=" ".join((p.get("title") or "").split()),
            abstract=" ".join((p.get("summary") or "").split()),
            authors=[a.get("name", "") for a in p.get("authors") or []],
            published=pub, url=f"https://arxiv.org/abs/{aid}", pdf_url=f"https://arxiv.org/pdf/{aid}",
            venue="arXiv", hf_upvotes=p.get("upvotes") or item.get("upvotes"),
            source_lanes={"field"}, source_reason="trending on HF Daily Papers",
        ))
    log.info("HF daily: %d papers", len(out))
    return out
