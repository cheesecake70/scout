"""Render the static notebook into a folder (served by GitHub Pages)."""
from __future__ import annotations

import json
import logging
import os
import shutil
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import Settings
from ..notes.parse import Note, load_notes
from ..storage import Storage

log = logging.getLogger(__name__)
HERE = Path(__file__).parent


def md(text: str) -> str:
    return markdown.markdown(text or "", extensions=["extra", "sane_lists"])


def issue_url(repo: str, template: str, **fields: str) -> str:
    from urllib.parse import urlencode
    q = {"template": template, **{k: v for k, v in fields.items() if v}}
    return f"https://github.com/{repo}/issues/new?{urlencode(q)}"


def _streak(notes: list[Note], today: date) -> int:
    days = {n.date for n in notes}
    d = today if today in days else today - timedelta(days=1)
    n = 0
    while d in days:
        n += 1
        d -= timedelta(days=1)
    return n


def build(settings: Settings, out: str = "site_build") -> int:
    st = Storage(settings)
    notes = load_notes(settings)
    today = st.load_today()
    want = [w for w in st.load_want() if not w.served]
    repo = os.environ.get("GITHUB_REPOSITORY", settings.site.base_url.strip("/").split("github.com/")[-1] if "github.com" in settings.site.base_url else "") or "OWNER/REPO"
    by_id = {n.id: n for n in notes}

    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["md"] = md
    env.globals.update(title=settings.site.title, repo=repo, issue_url=issue_url, by_id=by_id, today=date.today())

    outp = Path(out)
    if outp.exists():
        shutil.rmtree(outp)
    (outp / "paper").mkdir(parents=True)
    shutil.copytree(HERE / "static", outp / "static")

    def render(tpl: str, dest: str, **ctx) -> None:
        (outp / dest).write_text(env.get_template(tpl).render(**ctx))

    # path: chain gaps -> led_to picks that were read
    edges = []
    for n in notes:
        for t in n.led_to:
            if t in by_id:
                edges.append((n, by_id[t]))

    lanes = Counter(n.lane for n in notes)
    tags = Counter(t for n in notes for t in n.tags)
    weeks = Counter(n.date.isocalendar()[:2] for n in notes)
    stats = {
        "total": len(notes), "streak": _streak(notes, date.today()), "lanes": lanes.most_common(),
        "tags": tags.most_common(15), "gap_closed": sum(1 for n in notes if n.led_to and any(t in by_id for t in n.led_to)),
        "with_gaps": sum(1 for n in notes if n.gaps.strip()), "skips": len(st.state.get("skips", {})),
        "weekly": sorted(weeks.items())[-12:], "run_days": len(st.state.get("run_days", [])),
    }

    render("index.html", "index.html", today_=today, notes=notes[:5], stats=stats, stale=(today is not None and today.date < date.today()))
    render("notes.html", "notes.html", notes=notes)
    render("path.html", "path.html", notes=notes, edges=edges)
    render("later.html", "later.html", want=want, missed=st.state.get("missed", {}))
    render("stats.html", "stats.html", stats=stats)
    for n in notes:
        try:
            rel = n.path.relative_to(settings.root).as_posix()
        except ValueError:
            rel = n.path.name
        render("paper.html", f"paper/{n.slug}.html", n=n, rel=rel, led_from=[by_id[i] for i in n.led_from if i in by_id],
               led_to=[by_id[i] for i in n.led_to if i in by_id])
    # search index
    idx = [{"id": n.id, "slug": n.slug, "title": n.title, "date": n.date.isoformat(), "lane": n.lane, "tags": n.tags,
            "rating": n.rating, "text": (n.understood + " " + n.gaps)[:2000]} for n in notes]
    (outp / "search.json").write_text(json.dumps(idx))
    (outp / ".nojekyll").write_text("")
    log.info("site: %d notes, %d edges -> %s", len(notes), len(edges), outp)
    return 0
