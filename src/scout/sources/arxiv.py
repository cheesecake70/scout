from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

import feedparser

from ..models import Paper
from .http import get
from .ids import strip_arxiv_version

log = logging.getLogger(__name__)
API = "https://export.arxiv.org/api/query"


def _entry_to_paper(e) -> Paper:
    raw_id = e.id.rsplit("/", 1)[-1]
    aid = strip_arxiv_version(raw_id)
    pub = datetime(*e.published_parsed[:6], tzinfo=UTC).date() if getattr(e, "published_parsed", None) else None
    pdf = next((l.href for l in getattr(e, "links", []) if l.get("type") == "application/pdf"), f"https://arxiv.org/pdf/{aid}")
    cats = [t.term for t in getattr(e, "tags", [])]
    return Paper(
        id=aid, arxiv_id=aid,
        title=" ".join(e.title.split()),
        abstract=" ".join(e.summary.split()),
        authors=[a.name for a in getattr(e, "authors", [])],
        published=pub,
        url=f"https://arxiv.org/abs/{aid}",
        pdf_url=pdf,
        venue=f"arXiv {cats[0]}" if cats else "arXiv",
        doi=getattr(e, "arxiv_doi", None),
    )


def _query(q: str, *, max_results: int = 100, sort: str = "submittedDate", start: int = 0) -> list[Paper]:
    text = get(API, params={"search_query": q, "start": start, "max_results": max_results,
                            "sortBy": sort, "sortOrder": "descending"}, json=False, cache_hours=6)
    if not text:
        return []
    feed = feedparser.parse(text)
    return [_entry_to_paper(e) for e in feed.entries]


def recent(categories: list[str], lookback_days: int, *, max_results: int = 300) -> list[Paper]:
    """New submissions in the given categories over the last N days."""
    cat_q = " OR ".join(f"cat:{c}" for c in categories)
    out: list[Paper] = []
    start = 0
    since: date | None = None
    while start < max_results:
        batch = _query(f"({cat_q})", max_results=min(100, max_results - start), start=start)
        if not batch:
            break
        out.extend(batch)
        if since is None:
            newest = max((p.published for p in batch if p.published), default=date.today())
            # window is relative to the newest announcement, so weekends/holidays don't empty the feed
            since = newest - timedelta(days=lookback_days - 1)
        if batch[-1].published and batch[-1].published < since:
            break
        start += len(batch)
    since = since or date.today()
    papers = [p for p in out if p.published and p.published >= since]
    for p in papers:
        p.source_lanes.add("niche")
        p.source_reason = "new on arXiv"
    log.info("arXiv recent: %d papers in %s since %s", len(papers), ",".join(categories), since)
    return papers


def search(query: str, *, max_results: int = 25) -> list[Paper]:
    """Full-text-ish search (title/abstract) for a free-text query, newest first."""
    words = [w for w in query.replace('"', "").split() if len(w) > 2][:8]
    if not words:
        return []
    q = " AND ".join(f"all:{w}" for w in words)
    papers = _query(q, max_results=max_results, sort="relevance")
    for p in papers:
        p.source_reason = f"gap query: {query}"
    return papers


def by_id(arxiv_id: str) -> Paper | None:
    text = get(API, params={"id_list": strip_arxiv_version(arxiv_id), "max_results": 1}, json=False)
    if not text:
        return None
    feed = feedparser.parse(text)
    if not feed.entries:
        return None
    return _entry_to_paper(feed.entries[0])
