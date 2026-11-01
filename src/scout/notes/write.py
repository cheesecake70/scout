from __future__ import annotations

from datetime import date
from pathlib import Path

import frontmatter

from ..config import Settings
from ..models import Paper


def note_path(settings: Settings, paper_id: str, on: date) -> Path:
    safe = paper_id.replace("/", "_").replace(":", "_")
    return settings.notes_dir / f"{on:%Y}" / f"{on:%m}" / f"{safe}.md"


def write_note(settings: Settings, paper: Paper, *, understood: str, gaps: str, on: date,
               lane: str = "own", depth: str = "deep", rating: int | None = None, tags: list[str] | None = None,
               why: str = "", led_from: list[str] | None = None) -> Path:
    path = note_path(settings, paper.id, on)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": paper.id, "title": paper.title, "date": on.isoformat(), "lane": lane, "depth": depth,
        "url": paper.url, "pdf_url": paper.pdf_url, "authors": paper.authors[:8], "venue": paper.venue,
        "rating": rating, "tags": tags or [], "led_to": [], "led_from": led_from or [],
    }
    body = f"## What I understood\n\n{understood.strip()}\n\n## Gaps\n\n{gaps.strip()}\n"
    if why:
        body += f"\n## Why it was picked\n\n{why.strip()}\n"
    post = frontmatter.Post(body, **meta)
    path.write_text(frontmatter.dumps(post) + "\n")
    return path


def append_led_to(note_path_: Path, target_id: str) -> None:
    post = frontmatter.load(note_path_)
    led = list(post.metadata.get("led_to") or [])
    if target_id not in led:
        led.append(target_id)
        post.metadata["led_to"] = led
        note_path_.write_text(frontmatter.dumps(post) + "\n")
