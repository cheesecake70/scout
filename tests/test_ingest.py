from datetime import date
from pathlib import Path

from scout.config import load_settings
from scout.models import Paper, Pick, Today
from scout.notes.ingest_issue import ingest, parse_form
from scout.notes.parse import load_notes
from scout.storage import Storage, now

BODY = """### Paper

2501.00001

### What I understood

They replace attention with a cheaper mixing op and it holds up.

### Gaps

Why does the mixing op preserve long-range info? I don't get the proof.

### Rating

4 · good

### Tags

_No response_
"""


def _settings(tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.yaml").write_text("{}")
    (tmp_path / "config" / "profile.md").write_text("I like efficient transformers.")
    return load_settings(tmp_path)


def test_parse_form():
    f = parse_form(BODY)
    assert f["paper"] == "2501.00001"
    assert f["tags"] == ""
    assert f["rating"].startswith("4")


def test_ingest_read_from_today(tmp_path):
    s = _settings(tmp_path)
    st = Storage(s)
    paper = Paper(id="2501.00001", arxiv_id="2501.00001", title="Cheap Mixing", abstract="x", url="https://arxiv.org/abs/2501.00001")
    st.save_today(Today(date=date.today(), picks=[Pick(paper=paper, lane="niche", depth="deep", score=0.5, why="because")], generated_at=now()))
    b = tmp_path / "body.md"
    b.write_text(BODY)
    assert ingest(s, body_path=str(b), labels=["scout:read"]) == 0
    notes = load_notes(s)
    assert len(notes) == 1
    n = notes[0]
    assert n.title == "Cheap Mixing" and n.rating == 4 and n.lane == "niche"
    assert "preserve long-range" in n.gaps
    assert Storage(s).state["seen"]["2501.00001"]["status"] == "read"


def test_ingest_want_and_skip(tmp_path):
    s = _settings(tmp_path)
    b = tmp_path / "w.md"
    b.write_text("### Paper\n\nhttps://openreview.net/forum?id=abc123\n\n### Why (optional)\n\nlooks fun\n\n### By when (optional, YYYY-MM-DD)\n\n_No response_\n")
    assert ingest(s, body_path=str(b), labels=["scout:want"]) == 0
    items = Storage(s).load_want()
    assert len(items) == 1 and items[0].why == "looks fun"
    b.write_text("### Paper\n\nhttps://openreview.net/forum?id=zzz\n\n### Why (optional, helps the ranking)\n\nnope\n")
    assert ingest(s, body_path=str(b), labels=["scout:skip"]) == 0
    assert Storage(s).state["seen"]["s2:or-zzz"]["status"] == "skipped"
