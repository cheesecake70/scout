from datetime import date, timedelta

import numpy as np

from scout.config import load_settings
from scout.models import Paper
from scout.ranking.score import Scored
from scout.ranking.select import select
from scout.storage import Storage


def _s(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.yaml").write_text("load: {papers_per_day: 3, deep_picks: 1}\n")
    return load_settings(tmp_path)


def _scored(pid, lanes, niche=-1.0, neigh=-1.0, field=-1.0, vec=None):
    v = np.zeros(4, dtype=np.float32)
    v[ord(pid[0]) % 4] = 1.0
    return Scored(Paper(id=pid, title=pid, source_lanes=set(lanes), source_reason=""), vec if vec is not None else v,
                  0.5, 0.0, 1.0, False, niche, neigh, field)


def test_select_one_per_lane_and_depth(tmp_path):
    s = _s(tmp_path)
    scored = [_scored("a", {"niche"}, niche=0.9), _scored("b", {"niche"}, niche=0.8),
              _scored("c", {"neighbourhood"}, neigh=0.7), _scored("d", {"field"}, field=0.6)]
    picks = select(s, scored, want=None, essential=None, gap_note_ids=[])
    assert [p.lane for p in picks] == ["niche", "neighbourhood", "field"]
    assert [p.depth for p in picks] == ["deep", "skim", "skim"]
    assert picks[0].paper.id == "a"


def test_select_diversity_skips_near_duplicates(tmp_path):
    s = _s(tmp_path)
    same = np.array([1, 0, 0, 0], dtype=np.float32)
    scored = [_scored("a", {"niche"}, niche=0.9, vec=same), _scored("b", {"neighbourhood"}, neigh=0.9, vec=same),
              _scored("c", {"neighbourhood"}, neigh=0.5)]
    picks = select(s, scored, want=None, essential=None, gap_note_ids=[])
    assert [p.paper.id for p in picks[:2]] == ["a", "c"]


def test_want_takes_deep_slot(tmp_path):
    s = _s(tmp_path)
    w = Paper(id="w", title="wanted")
    picks = select(s, [_scored("a", {"niche"}, niche=0.9)], want=w, essential=None, gap_note_ids=[])
    assert picks[0].lane == "want" and picks[0].depth == "deep"
    assert picks[1].depth == "skim"


def test_no_backlog_missed_cooldown(tmp_path):
    s = _s(tmp_path)
    st = Storage(s)
    today = date.today()
    st.mark_missed("x", today - timedelta(days=3))
    assert st.is_excluded("x", today, cooldown_days=14)
    assert not st.is_excluded("x", today + timedelta(days=12), cooldown_days=14)
    st.mark_seen("x", "read")
    assert st.is_excluded("x", today + timedelta(days=400), cooldown_days=14)
    assert "x" not in st.state["missed"]
