"""Notes are markdown files with YAML front-matter, one per paper, under notes/YYYY/MM/<id>.md."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import frontmatter

from ..config import Settings

SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Note:
    path: Path
    id: str
    title: str
    date: date
    lane: str = "own"
    depth: str = "deep"
    url: str = ""
    pdf_url: str = ""
    authors: list[str] = field(default_factory=list)
    venue: str = ""
    rating: int | None = None
    tags: list[str] = field(default_factory=list)
    led_to: list[str] = field(default_factory=list)
    led_from: list[str] = field(default_factory=list)
    understood: str = ""
    gaps: str = ""
    why: str = ""

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.id.lower()).strip("-")


def _sections(body: str) -> dict[str, str]:
    parts = SECTION_RE.split(body)
    out: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].strip().lower()] = parts[i + 1].strip()
    return out


def parse_note(path: Path) -> Note:
    post = frontmatter.load(path)
    m = post.metadata
    secs = _sections(post.content)
    d = m.get("date")
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return Note(
        path=path, id=str(m.get("id", path.stem)), title=m.get("title", path.stem), date=d or date.today(),
        lane=m.get("lane", "own"), depth=m.get("depth", "deep"), url=m.get("url", ""), pdf_url=m.get("pdf_url", ""),
        authors=list(m.get("authors") or []), venue=m.get("venue", ""), rating=m.get("rating"),
        tags=list(m.get("tags") or []), led_to=list(m.get("led_to") or []), led_from=list(m.get("led_from") or []),
        understood=secs.get("what i understood", secs.get("understood", "")),
        gaps=secs.get("gaps", secs.get("what gaps i found", "")),
        why=secs.get("why it was picked", ""),
    )


def load_notes(settings: Settings) -> list[Note]:
    notes = [parse_note(p) for p in sorted(settings.notes_dir.rglob("*.md"))]
    notes.sort(key=lambda n: (n.date, n.path.name), reverse=True)
    return notes


def recent_gaps(notes: list[Note], days: int = 7, today: date | None = None) -> list[tuple[Note, str]]:
    today = today or date.today()
    return [(n, n.gaps) for n in notes if n.gaps.strip() and (today - n.date).days <= days]
