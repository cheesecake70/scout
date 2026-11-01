from __future__ import annotations

import logging
import os
from datetime import datetime

from ..models import Paper
from .http import get

log = logging.getLogger(__name__)
API = "https://api2.openreview.net/notes"


def accepted(venue_id: str, *, limit: int = 200) -> list[Paper]:
    """Accepted notes for an OpenReview venue id like 'ICLR.cc/2026/Conference'.

    OpenReview requires a logged-in token for API access; set OPENREVIEW_TOKEN. Without it this source is skipped
    and conference papers come from Semantic Scholar's venue filter instead.
    """
    tok = os.environ.get("OPENREVIEW_TOKEN")
    if not tok:
        log.debug("OPENREVIEW_TOKEN not set; skipping OpenReview")
        return []
    d = get(API, params={"content.venueid": venue_id, "limit": limit},
            headers={"Authorization": f"Bearer {tok}"}, cache_hours=48)
    out: list[Paper] = []
    for n in (d or {}).get("notes", []):
        c = n.get("content") or {}

        def val(k, _c=c):
            v = _c.get(k)
            return v.get("value") if isinstance(v, dict) else v

        title = val("title")
        if not title:
            continue
        nid = n.get("id")
        pub = None
        if n.get("pdate"):
            pub = datetime.fromtimestamp(n["pdate"] / 1000).date()
        elif n.get("cdate"):
            pub = datetime.fromtimestamp(n["cdate"] / 1000).date()
        out.append(Paper(
            id=f"s2:or-{nid}", title=" ".join(title.split()), abstract=" ".join((val("abstract") or "").split()),
            authors=list(val("authors") or []), published=pub,
            url=f"https://openreview.net/forum?id={nid}", pdf_url=f"https://openreview.net/pdf?id={nid}",
            venue=venue_id.split("/")[0].replace(".cc", ""),
            source_lanes={"field"}, source_reason=f"accepted at {venue_id}",
        ))
    log.info("OpenReview %s: %d notes", venue_id, len(out))
    return out
