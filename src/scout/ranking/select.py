"""Turn scored candidates into today's 1-3 picks across lanes, with diversity and depth."""
from __future__ import annotations

import logging

from ..config import Settings
from ..models import Paper, Pick
from .score import Scored

log = logging.getLogger(__name__)


def _diverse(chosen: list[Scored], cand: Scored, max_cos: float) -> bool:
    return all(float(cand.vec @ c.vec) < max_cos for c in chosen)


def select(settings: Settings, scored: list[Scored], *, want: Paper | None = None,
           essential: Scored | None = None, gap_note_ids: list[str]) -> list[Pick]:
    L = settings.load
    n = max(1, min(3, L.papers_per_day))
    max_cos = settings.ranking.diversity_max_cosine
    chosen: list[Scored] = []
    picks: list[Pick] = []

    # deep slot: want > essential > best niche/neighbourhood
    if want is not None:
        picks.append(Pick(paper=want, lane="want", depth="deep", score=1.0))
    elif essential is not None:
        chosen.append(essential)
        picks.append(Pick(paper=essential.paper, lane="essential", depth="deep", score=essential.field))

    pool = sorted(scored, key=lambda s: max(s.niche, s.neighbourhood), reverse=True)
    lane_order = ["niche", "neighbourhood", "field", "niche", "neighbourhood"]
    for lane in lane_order:
        if len(picks) >= n:
            break
        key = {"niche": lambda s: s.niche, "neighbourhood": lambda s: s.neighbourhood, "field": lambda s: s.field}[lane]
        ranked = sorted((s for s in pool if key(s) > -1.0 and s not in chosen), key=key, reverse=True)
        for s in ranked:
            if _diverse(chosen, s, max_cos):
                chosen.append(s)
                depth = "deep" if len([p for p in picks if p.depth == "deep"]) < L.deep_picks else "skim"
                led_from = gap_note_ids if (lane == "niche" and s.sim_gaps > 0.35 and "gap query" in s.paper.source_reason) else []
                picks.append(Pick(paper=s.paper, lane=lane, depth=depth, score=round(key(s), 4), led_from=led_from))
                break
    return picks[:n]
