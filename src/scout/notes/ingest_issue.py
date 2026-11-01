"""Turn a GitHub Issue Form body into a note / want item / skip / bootstrap votes.

Issue Forms render as markdown: '### <Label>\n\n<value>\n\n'. Empty fields render '_No response_'.
Writes a short summary to data/last_ingest.md for the workflow to post as a comment.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

from ..config import Settings
from ..models import Paper
from ..sources import arxiv
from ..sources import semantic_scholar as s2
from ..sources.ids import parse_ref
from ..storage import Storage
from .write import write_note

log = logging.getLogger(__name__)
FIELD_RE = re.compile(r"^###\s+(.+?)\s*\n(.*?)(?=^###\s|\Z)", re.MULTILINE | re.DOTALL)


def parse_form(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in FIELD_RE.finditer(body):
        k = m.group(1).strip().lower()
        v = m.group(2).strip()
        if v == "_No response_":
            v = ""
        out[k] = v
    return out


def resolve_paper(settings: Settings, ref: str) -> Paper | None:
    """Prefer today's picks (already have metadata), else look the paper up."""
    st = Storage(settings)
    r = parse_ref(ref)
    today = st.load_today()
    if today:
        for p in today.picks:
            if p.paper.id == r["value"] or p.paper.arxiv_id == r["value"] or p.paper.url == ref.strip():
                return p.paper
    if r["kind"] == "arxiv":
        return arxiv.by_id(r["value"]) or s2.lookup(r["value"])
    if r["kind"] == "doi":
        return s2.lookup(f"doi:{r['value']}")
    if r["kind"] == "s2":
        return s2.lookup(f"s2:{r['value']}")
    if r["kind"] == "openreview":
        return Paper(id=f"s2:or-{r['value']}", title=ref, url=f"https://openreview.net/forum?id={r['value']}")
    # bare URL: try S2 search by the URL's last path piece as a last resort
    return Paper(id=f"url:{abs(hash(ref)) % 10**10}", title=ref, url=ref)


def _rating(v: str) -> int | None:
    m = re.match(r"\s*([1-5])", v or "")
    return int(m.group(1)) if m else None


def ingest(settings: Settings, *, body_path: str, labels: list[str], title: str = "", dry_run: bool = False) -> int:
    body = Path(body_path).read_text()
    f = parse_form(body)
    st = Storage(settings)
    today = date.today()
    labels = [l.strip() for l in labels if l.strip()]
    kind = next((l.split(":", 1)[1] for l in labels if l.startswith("scout:")), None)
    if kind is None:
        kind = title.split(":", 1)[0].strip().lower() if ":" in title else "read"
    summary = ""

    if kind in ("read", "log"):
        paper = resolve_paper(settings, f.get("paper", ""))
        if not paper:
            summary = f"⚠️ Could not resolve paper `{f.get('paper')}`. Edit the issue with an arXiv id or DOI and re-add the label."
            return _finish(settings, summary, dry_run, ok=False)
        pick = _today_pick(st, paper.id)
        lane = pick.lane if pick else "own"
        depth = pick.depth if pick else "deep"
        why = pick.why if pick else ""
        led_from = pick.led_from if pick else []
        tags = [t.strip() for t in re.split(r"[,\s]+", f.get("tags", "")) if t.strip()]
        path = None
        if not dry_run:
            path = write_note(settings, paper, understood=f.get("what i understood", ""), gaps=f.get("gaps", ""),
                              on=today, lane=lane, depth=depth, rating=_rating(f.get("rating", "")), tags=tags,
                              why=why, led_from=led_from)
            st.mark_seen(paper.id, "read", today)
            st.save_state()
        summary = f"✅ Logged **{paper.title}** → `{path.relative_to(settings.root) if path else '(dry run)'}`"
        if f.get("gaps"):
            summary += "\n\nYour gaps will shape tomorrow's picks."

    elif kind == "skip":
        paper = resolve_paper(settings, f.get("paper", ""))
        pid = paper.id if paper else f.get("paper", "")
        if not dry_run:
            st.mark_seen(pid, "skipped", today)
            st.state.setdefault("skips", {})[pid] = {"reason": f.get("why (optional, helps the ranking)", ""),
                                                      "title": paper.title if paper else pid, "abstract": paper.abstract if paper else ""}
            st.save_state()
        summary = f"⏭ Skipped **{paper.title if paper else pid}**. It won't come back."

    elif kind == "want":
        paper = resolve_paper(settings, f.get("paper", ""))
        from ..models import WantItem
        bw = f.get("by when (optional, yyyy-mm-dd)", "")
        by_when = None
        if bw:
            try:
                by_when = date.fromisoformat(bw[:10])
            except ValueError:
                by_when = None
        item = WantItem(id=paper.id if paper else f.get("paper", ""), title=paper.title if paper else "",
                        url=paper.url if paper else f.get("paper", ""), why=f.get("why (optional)", ""),
                        by_when=by_when, added=today)
        if not dry_run:
            items = st.load_want()
            if all(i.id != item.id for i in items):
                items.append(item)
            st.save_want(items)
            st.mark_seen(item.id, "want", today)
            st.save_state()
        summary = f"📌 Queued **{item.title or item.id}**. It'll take a deep slot within the next few days."

    elif kind == "bootstrap":
        votes = f.get("votes", body)
        n = 0
        for line in votes.splitlines():
            up = re.search(r"\[x\]\s*👍", line, re.IGNORECASE)
            down = re.search(r"\[x\]\s*👎", line, re.IGNORECASE)
            m = re.search(r"👎\s*(.+?)\s*\((https?://\S+)\)", line)
            if not m or not (up or down):
                continue
            t, url = m.group(1), m.group(2)
            r = parse_ref(url)
            pid = r["value"] if r["kind"] == "arxiv" else url
            st.state.setdefault("feedback", {})[pid] = {"title": t, "vote": "up" if up else "down", "url": url}
            st.mark_seen(pid, "liked" if up else "disliked", today)
            n += 1
        if not dry_run:
            st.save_state()
        summary = f"🌱 Recorded {n} votes. Your profile now leans toward what you liked."
    else:
        summary = f"⚠️ Unknown issue kind `{kind}`; labels were {labels}."
        return _finish(settings, summary, dry_run, ok=False)
    return _finish(settings, summary, dry_run, ok=True)


def _today_pick(st: Storage, pid: str):
    t = st.load_today()
    if not t:
        return None
    return next((p for p in t.picks if p.paper.id == pid), None)


def _finish(settings: Settings, summary: str, dry_run: bool, ok: bool) -> int:
    print(summary)
    if not dry_run:
        (settings.data_dir / "last_ingest.md").write_text(summary + "\n")
    return 0 if ok else 1
