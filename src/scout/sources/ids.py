"""Parse user-supplied paper references (URLs, arXiv ids, DOIs) into a canonical id."""
from __future__ import annotations

import re

ARXIV_RE = re.compile(r"(?:arxiv\.org/(?:abs|pdf|html)/|arXiv:)?(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", re.IGNORECASE)
OLD_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([a-z\-]+(?:\.[A-Z]{2})?/\d{7})", re.IGNORECASE)
DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
S2_RE = re.compile(r"semanticscholar\.org/paper/(?:[^/]+/)?([0-9a-f]{40})", re.IGNORECASE)
OPENREVIEW_RE = re.compile(r"openreview\.net/(?:forum|pdf)\?id=([\w\-]+)", re.IGNORECASE)


def strip_arxiv_version(aid: str) -> str:
    return re.sub(r"v\d+$", "", aid)


def parse_ref(text: str) -> dict[str, str]:
    """Return {kind, value} where kind in {arxiv, doi, s2, openreview, url}."""
    t = text.strip()
    if m := S2_RE.search(t):
        return {"kind": "s2", "value": m.group(1)}
    if m := OPENREVIEW_RE.search(t):
        return {"kind": "openreview", "value": m.group(1)}
    if m := OLD_ARXIV_RE.search(t):
        return {"kind": "arxiv", "value": m.group(1)}
    if m := ARXIV_RE.search(t):
        return {"kind": "arxiv", "value": strip_arxiv_version(m.group(1))}
    if m := DOI_RE.search(t):
        return {"kind": "doi", "value": m.group(1).rstrip(".,;)")}
    return {"kind": "url", "value": t}


def canonical_id(arxiv_id: str | None = None, doi: str | None = None, s2_id: str | None = None) -> str:
    if arxiv_id:
        return strip_arxiv_version(arxiv_id)
    if doi:
        return f"doi:{doi.lower()}"
    if s2_id:
        return f"s2:{s2_id}"
    raise ValueError("no identifier")
