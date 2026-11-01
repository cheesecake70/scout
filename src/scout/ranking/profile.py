"""Profile vector (who you are + what you liked) and gap vector (what you recently didn't get)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from ..config import Settings
from ..notes.parse import Note, recent_gaps
from .embed import embed, unit


@dataclass
class Vectors:
    profile: np.ndarray
    gaps: np.ndarray | None
    topics: list[tuple[str, float, np.ndarray]]
    gap_notes: list[Note]


def build_vectors(settings: Settings, notes: list[Note], today: date | None = None) -> Vectors:
    model = settings.ranking.embedding_model
    today = today or date.today()

    texts = [settings.profile_text or "machine learning research"]
    weights = [2.0]
    for n in notes[:60]:
        if n.lane == "skip":
            continue
        txt = f"{n.title}\n{n.understood}"
        r = n.rating or 3
        w = {1: -0.6, 2: -0.2, 3: 0.4, 4: 0.8, 5: 1.0}.get(r, 0.4)
        texts.append(txt)
        weights.append(w)
    # bootstrap votes and skips live in state.json (no note file for those)
    from ..storage import Storage
    st = Storage(settings).state
    for fb in list(st.get("feedback", {}).values())[:60]:
        texts.append(fb.get("title", ""))
        weights.append(0.6 if fb.get("vote") == "up" else -0.5)
    for sk in list(st.get("skips", {}).values())[:40]:
        texts.append(f"{sk.get('title', '')}\n{sk.get('abstract', '')[:500]}")
        weights.append(-0.4)
    vecs = embed(texts, model)
    prof = unit(np.sum(vecs * np.array(weights, dtype=np.float32)[:, None], axis=0))

    gap_items = recent_gaps(notes, days=7, today=today)
    gaps_vec = None
    if gap_items:
        gv = embed([g for _, g in gap_items], model)
        rec = np.array([0.5 ** (today - n.date).days for n, _ in gap_items], dtype=np.float32)
        gaps_vec = unit(np.sum(gv * rec[:, None], axis=0))

    topic_names = list(settings.topics.keys())
    topic_vecs = embed(topic_names, model) if topic_names else np.zeros((0, prof.shape[0]), dtype=np.float32)
    topics = [(name, float(settings.topics[name]), topic_vecs[i]) for i, name in enumerate(topic_names)]
    return Vectors(profile=prof, gaps=gaps_vec, topics=topics, gap_notes=[n for n, _ in gap_items])
