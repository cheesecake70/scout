from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import Settings
from ..models import Paper
from .embed import embed
from .profile import Vectors


@dataclass
class Scored:
    paper: Paper
    vec: np.ndarray
    sim_profile: float
    sim_gaps: float
    topic_weight: float
    popular: bool
    niche: float
    neighbourhood: float
    field: float


def score_all(settings: Settings, papers: list[Paper], V: Vectors) -> list[Scored]:
    if not papers:
        return []
    r = settings.ranking
    vecs = embed([p.text() for p in papers], r.embedding_model)
    sp = vecs @ V.profile
    sg = vecs @ V.gaps if V.gaps is not None else np.zeros(len(papers), dtype=np.float32)
    if V.topics:
        T = np.stack([t[2] for t in V.topics])
        W = np.array([t[1] for t in V.topics], dtype=np.float32)
        topic_sim = vecs @ T.T                       # (n, k)
        # weight = weight of the best-matching topic, softened so unmatched papers aren't zeroed
        best = topic_sim.argmax(axis=1)
        tw = 0.5 + 0.5 * W[best]
    else:
        tw = np.ones(len(papers), dtype=np.float32)

    out: list[Scored] = []
    for i, p in enumerate(papers):
        popular = bool((p.hf_upvotes or 0) >= 20 or (p.citation_count or 0) >= r.popularity_citation_threshold)
        niche = float(sp[i] * tw[i] + r.gap_weight * sg[i] - (r.popularity_penalty if popular else 0.0))
        # neighbourhood: proximity is implicit in how the candidate was found; weight by profile fit
        neigh = float(sp[i]) if "neighbourhood" in p.source_lanes else -1.0
        # field: trending / citations with a relevance floor
        trend = 0.0
        if p.hf_upvotes:
            trend += min(p.hf_upvotes, 200) / 200.0
        if p.citation_count:
            trend += min(p.citation_count, 2000) / 2000.0
        field = float(trend + 0.3 * sp[i]) if ("field" in p.source_lanes and sp[i] >= r.relevance_floor) else -1.0
        out.append(Scored(p, vecs[i], float(sp[i]), float(sg[i]), float(tw[i]), popular, niche, neigh, field))
    return out
