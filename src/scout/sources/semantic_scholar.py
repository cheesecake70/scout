from __future__ import annotations

import logging
import os
import time
from datetime import date

from ..models import Paper
from .http import get as _get
from .http import post as _post
from .ids import canonical_id, strip_arxiv_version

log = logging.getLogger(__name__)
API = "https://api.semanticscholar.org/graph/v1"
REC = "https://api.semanticscholar.org/recommendations/v1"
FIELDS = "paperId,externalIds,title,abstract,authors,year,publicationDate,venue,citationCount,influentialCitationCount,openAccessPdf,url"


def _headers() -> dict:
    key = os.environ.get("S2_API_KEY")
    return {"x-api-key": key} if key else {}


_last_call = 0.0


def _throttle() -> None:
    """Anonymous S2 access is shared and tight; keep >=1.2s between calls (0.1s with a key)."""
    global _last_call
    gap = 0.1 if os.environ.get("S2_API_KEY") else 3.0
    wait = _last_call + gap - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()


def get(*a, **kw):
    _throttle()
    kw.setdefault("retries", 5)
    return _get(*a, **kw)


def post(*a, **kw):
    _throttle()
    kw.setdefault("retries", 5)
    kw.pop("cache_hours", None)
    return _post(*a, **kw)


def _to_paper(d: dict) -> Paper | None:
    if not d or not d.get("title"):
        return None
    ext = d.get("externalIds") or {}
    aid = ext.get("ArXiv")
    doi = ext.get("DOI")
    try:
        cid = canonical_id(aid, doi, d.get("paperId"))
    except ValueError:
        return None
    pub = None
    if d.get("publicationDate"):
        try:
            pub = date.fromisoformat(d["publicationDate"])
        except ValueError:
            pub = None
    elif d.get("year"):
        pub = date(int(d["year"]), 1, 1)
    pdf = (d.get("openAccessPdf") or {}).get("url") or (f"https://arxiv.org/pdf/{aid}" if aid else "")
    return Paper(
        id=cid, arxiv_id=strip_arxiv_version(aid) if aid else None, doi=doi, s2_id=d.get("paperId"),
        title=" ".join(d["title"].split()), abstract=" ".join((d.get("abstract") or "").split()),
        authors=[a.get("name", "") for a in d.get("authors") or []],
        published=pub, url=d.get("url") or (f"https://arxiv.org/abs/{aid}" if aid else ""), pdf_url=pdf,
        venue=d.get("venue") or ("arXiv" if aid else ""),
        citation_count=d.get("citationCount"), influential_citation_count=d.get("influentialCitationCount"),
    )


def _s2_ref(p_or_id: str) -> str:
    """Accept canonical id or raw; map to S2 id syntax."""
    x = p_or_id
    if x.startswith("doi:"):
        return f"DOI:{x[4:]}"
    if x.startswith("s2:"):
        return x[3:]
    return f"arXiv:{x}"


def lookup(ref: str) -> Paper | None:
    d = get(f"{API}/paper/{_s2_ref(ref)}", params={"fields": FIELDS}, headers=_headers(), cache_hours=24 * 7)
    return _to_paper(d) if d else None


def batch_lookup(refs: list[str]) -> list[Paper]:
    out: list[Paper] = []
    for i in range(0, len(refs), 100):
        chunk = [_s2_ref(r) for r in refs[i:i + 100]]
        d = post(f"{API}/paper/batch", body={"ids": chunk}, params={"fields": FIELDS}, headers=_headers(), cache_hours=20)
        for item in d or []:
            p = _to_paper(item)
            if p:
                out.append(p)
    return out


def search(query: str, *, limit: int = 20, year_from: int | None = None) -> list[Paper]:
    params = {"query": query, "limit": limit, "fields": FIELDS}
    if year_from:
        params["year"] = f"{year_from}-"
    d = get(f"{API}/paper/search", params=params, headers=_headers(), cache_hours=20)
    papers = [p for p in (_to_paper(x) for x in (d or {}).get("data", [])) if p]
    for p in papers:
        p.source_reason = f"gap query: {query}"
    return papers


def neighbours(ref: str, *, limit: int = 30) -> list[Paper]:
    """References + citations of a paper, one hop."""
    out: list[Paper] = []
    for kind, key in (("references", "citedPaper"), ("citations", "citingPaper")):
        d = get(f"{API}/paper/{_s2_ref(ref)}/{kind}", params={"fields": FIELDS, "limit": limit}, headers=_headers(), cache_hours=20)
        for item in (d or {}).get("data", []):
            p = _to_paper(item.get(key) or {})
            if p:
                p.source_reason = f"{'cited by' if kind == 'references' else 'cites'} {ref}"
                out.append(p)
    return out


def recommendations(positive: list[str], negative: list[str] | None = None, *, limit: int = 40) -> list[Paper]:
    body = {"positivePaperIds": [_s2_ref(r) for r in positive], "negativePaperIds": [_s2_ref(r) for r in negative or []]}
    d = post(f"{REC}/papers", body=body, params={"fields": FIELDS, "limit": limit}, headers=_headers(), cache_hours=20)
    papers = [p for p in (_to_paper(x) for x in (d or {}).get("recommendedPapers", [])) if p]
    for p in papers:
        p.source_reason = "S2 recommendation from your reads"
    return papers


def by_author(author_name: str, *, limit: int = 15) -> list[Paper]:
    d = get(f"{API}/author/search", params={"query": author_name, "fields": "authorId,name,paperCount", "limit": 3}, headers=_headers(), cache_hours=20)
    cands = (d or {}).get("data", [])
    if not cands:
        return []
    best = max(cands, key=lambda a: a.get("paperCount") or 0)
    d = get(f"{API}/author/{best['authorId']}/papers", params={"fields": FIELDS, "limit": limit}, headers=_headers(), cache_hours=20)
    papers = [p for p in (_to_paper(x) for x in (d or {}).get("data", [])) if p]
    for p in papers:
        p.source_reason = f"new from {author_name}"
    return papers


def essentials(topic: str, *, limit: int = 30) -> list[Paper]:
    """Highly cited papers on a topic, any year. Candidate pool for the classics slot."""
    d = get(f"{API}/paper/search", params={"query": topic, "limit": limit, "fields": FIELDS,
                                            "minCitationCount": 300}, headers=_headers(), cache_hours=20)
    papers = [p for p in (_to_paper(x) for x in (d or {}).get("data", [])) if p]
    for p in papers:
        p.source_reason = f"essential on '{topic}'"
    return papers


def venue_papers(venue: str, year: int, *, limit: int = 100, query: str = "language model OR vision OR learning") -> list[Paper]:
    """Papers from a conference via S2's venue filter (OpenReview blocks anonymous API access)."""
    d = get(f"{API}/paper/search", params={"query": query, "venue": venue, "year": str(year), "limit": limit,
                                            "fields": FIELDS}, headers=_headers(), cache_hours=48)
    papers = [p for p in (_to_paper(x) for x in (d or {}).get("data", [])) if p]
    for p in papers:
        p.source_lanes.add("field")
        p.source_reason = f"accepted at {venue} {year}"
    return papers
