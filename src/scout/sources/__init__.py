from __future__ import annotations

from ..models import Paper, normalise_title


def dedup(papers: list[Paper]) -> list[Paper]:
    """Merge duplicates by arXiv id, DOI, or normalised title. Keeps the richest record and unions lanes."""
    by_key: dict[str, Paper] = {}
    order: list[str] = []

    def keys(p: Paper) -> list[str]:
        k = []
        if p.arxiv_id:
            k.append(f"a:{p.arxiv_id}")
        if p.doi:
            k.append(f"d:{p.doi.lower()}")
        if p.s2_id:
            k.append(f"s:{p.s2_id}")
        k.append(f"t:{normalise_title(p.title)}")
        return k

    alias: dict[str, str] = {}
    for p in papers:
        hit = next((alias[k] for k in keys(p) if k in alias), None)
        if hit is None:
            hit = p.id
            by_key[hit] = p
            order.append(hit)
        else:
            q = by_key[hit]
            # merge: fill blanks, prefer arXiv canonical id, union lanes
            for f in ("abstract", "pdf_url", "url", "venue", "doi", "s2_id", "arxiv_id", "published"):
                if not getattr(q, f) and getattr(p, f):
                    setattr(q, f, getattr(p, f))
            for f in ("citation_count", "influential_citation_count", "hf_upvotes"):
                if getattr(q, f) is None and getattr(p, f) is not None:
                    setattr(q, f, getattr(p, f))
            if not q.authors and p.authors:
                q.authors = p.authors
            q.source_lanes |= p.source_lanes
            if p.source_reason and p.source_reason not in q.source_reason:
                q.source_reason = f"{q.source_reason}; {p.source_reason}".strip("; ")
            if q.arxiv_id and q.id != q.arxiv_id:
                q.id = q.arxiv_id
        for k in keys(p):
            alias[k] = hit
    return [by_key[k] for k in order]
