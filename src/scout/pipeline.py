"""The daily run: gather candidates per lane, score, select, explain, persist."""
from __future__ import annotations

import logging
from datetime import date

from .config import Settings
from .models import Paper, Today
from .notes.parse import load_notes
from .ranking.profile import build_vectors
from .ranking.score import score_all
from .ranking.select import select
from .sources import arxiv, dedup, hf_daily, openreview
from .sources import semantic_scholar as s2
from .storage import Storage, now

log = logging.getLogger(__name__)


def gather(settings: Settings, notes, gap_queries: list[str]) -> list[Paper]:
    S = settings.sources
    cands: list[Paper] = []

    # niche: fresh arXiv
    cands += arxiv.recent(S.arxiv_categories, S.arxiv_lookback_days, max_results=500)

    # niche: gap-driven search
    for q in gap_queries[:3]:
        for p in arxiv.search(q, max_results=15) + s2.search(q, limit=10, year_from=date.today().year - 3):
            p.source_lanes.add("niche")
            cands.append(p)

    # neighbourhood: citation walk + S2 recommendations from recent reads
    read_ids = [n.id for n in notes if n.lane != "skip"][: S.neighbourhood_recent_reads]
    s2_ok = [i for i in read_ids if not i.startswith("s2:or-")]
    if s2_ok:
        for p in s2.recommendations(s2_ok, limit=30):
            p.source_lanes.add("neighbourhood")
            cands.append(p)
        for rid in s2_ok[:2]:
            for p in s2.neighbours(rid, limit=15):
                p.source_lanes.add("neighbourhood")
                cands.append(p)
    # neighbourhood: authors you rated highly
    liked_authors: list[str] = []
    for n in notes[:20]:
        if (n.rating or 0) >= S.author_follow_min_rating:
            liked_authors += n.authors[:2]
    for a in dict.fromkeys(liked_authors):
        if len(liked_authors) > 4:
            break
        for p in s2.by_author(a, limit=10):
            p.source_lanes.add("neighbourhood")
            cands.append(p)

    # field: trending + conferences
    if S.hf_daily:
        cands += hf_daily.trending(limit=40)
    for v in S.venues:
        try:
            cands += s2.venue_papers(v["name"], int(v["year"]), limit=50)
        except (KeyError, TypeError, ValueError):
            log.warning("bad venue entry %r", v)
    for v in S.openreview_venues:
        cands += openreview.accepted(v)

    before = len(cands)
    cands = dedup(cands)
    cands = [c for c in cands if c.abstract or c.title]
    log.info("candidates: %d raw -> %d unique", before, len(cands))
    return cands


def essential_candidates(settings: Settings) -> list[Paper]:
    out: list[Paper] = []
    for topic in list(settings.topics.keys())[:2]:
        out += s2.essentials(topic, limit=20)
    return dedup(out)


def run_daily(settings: Settings, *, dry_run: bool = False, no_llm: bool = False,
              force_want: bool = False, force_essential: bool = False) -> int:
    st = Storage(settings)
    today = date.today()
    notes = load_notes(settings)
    log.info("notes on file: %d", len(notes))

    # no backlog: yesterday's unread picks become 'missed'
    prev = st.load_today()
    if prev and prev.date < today:
        for p in prev.picks:
            if p.lane != "want":
                st.mark_missed(p.paper.id, prev.date)

    V = build_vectors(settings, notes, today)
    gap_queries: list[str] = []
    llm = None
    if not no_llm:
        from .llm.router import get_llm
        llm = get_llm(settings)
    if V.gap_notes:
        gap_text = "\n\n".join(f"- ({n.title}) {n.gaps}" for n in V.gap_notes[:5])
        if llm:
            gap_queries = llm.gap_queries(gap_text) or []
        gap_queries = [q.strip("-•* \n") for q in gap_queries]
        gap_queries = [q for q in gap_queries if len(q) > 6]
        if not gap_queries:
            gap_queries = [n.gaps.strip("-•* \n").split(".")[0][:120] for n in V.gap_notes[:2]]
    log.info("gap queries: %s", gap_queries)

    cands = gather(settings, notes, gap_queries)
    L = settings.load
    cands = [c for c in cands if not st.is_excluded(c.id, today, L.missed_cooldown_days)]
    scored = score_all(settings, cands, V)

    # want queue
    want_paper: Paper | None = None
    want_items = st.load_want()
    pending = [w for w in want_items if not w.served]
    last_want = st.state.get("last_want")
    due = force_want or (pending and (not last_want or (today - date.fromisoformat(last_want)).days >= L.want_every_n_days))
    if pending and due:
        pending.sort(key=lambda w: (w.by_when or date.max, w.added))
        w = pending[0]
        want_paper = s2.lookup(w.id) or arxiv.by_id(w.id) or Paper(id=w.id, title=w.title or w.id, url=w.url)
        want_paper.source_reason = f"you asked for it: {w.why}".strip(": ")

    # essentials
    essential = None
    last_ess = st.state.get("last_essential")
    ess_due = force_essential or (not last_ess or (today - date.fromisoformat(last_ess)).days >= L.essentials_every_n_days)
    if want_paper is None and ess_due:
        ess = [e for e in essential_candidates(settings) if not st.is_excluded(e.id, today, 10**6)]
        ess_scored = score_all(settings, ess, V)
        ess_scored = [e for e in ess_scored if e.sim_profile >= settings.ranking.relevance_floor]
        if ess_scored:
            if llm:
                choice = llm.choose_essential([e.paper for e in ess_scored[:12]], settings.profile_text)
                essential = next((e for e in ess_scored if e.paper.id == choice), None)
            essential = essential or max(ess_scored, key=lambda e: (e.paper.influential_citation_count or 0, e.sim_profile))
            essential.field = max(essential.field, 1.0)

    gap_ids = [n.id for n in V.gap_notes[:5]]
    picks = select(settings, scored, want=want_paper, essential=essential, gap_note_ids=gap_ids)

    # explanations
    for p in picks:
        if llm:
            why, payoff = llm.explain(p.paper, settings.profile_text, V.gap_notes[:3], p.lane)
            p.why, p.payoff = why, payoff
        if not p.why:
            p.why = p.paper.source_reason or "Matched your profile."
        if not p.payoff:
            p.payoff = (p.paper.abstract[:280] + "…") if p.paper.abstract else ""

    T = Today(date=today, picks=picks, generated_at=now(), gap_queries=gap_queries)
    _print_today(T)
    if dry_run:
        log.info("dry run: nothing written")
        return 0

    st.save_today(T)
    if want_paper is not None:
        for w in want_items:
            if w.id == want_paper.id:
                w.served = True
        st.save_want(want_items)
        st.state["last_want"] = today.isoformat()
    if essential is not None:
        st.state["last_essential"] = today.isoformat()
    st.state["run_days"] = sorted(set(st.state["run_days"] + [today.isoformat()]))[-400:]
    # led_to links: gap notes -> today's gap-driven picks
    from .notes.write import append_led_to
    for p in picks:
        for nid in p.led_from:
            for n in notes:
                if n.id == nid:
                    append_led_to(n.path, p.paper.id)
    st.save_state()
    return 0


def _print_today(T: Today) -> None:
    print(f"\n=== scout · {T.date:%A %d %b %Y} ===")
    if T.gap_queries:
        print("gap queries:", "; ".join(T.gap_queries))
    for i, p in enumerate(T.picks, 1):
        pp = p.paper
        print(f"\n{i}. [{p.lane} · {p.depth}] {pp.title}")
        print(f"   {', '.join(pp.authors[:3])}{' et al.' if len(pp.authors) > 3 else ''} · {pp.venue} · {pp.published}")
        print(f"   {pp.url}")
        print(f"   why: {p.why}")
        print(f"   payoff: {p.payoff}")
        print(f"   (score {p.score}; via {pp.source_reason})")
    print()


def bootstrap(settings: Settings) -> int:
    """Print ~20 diverse seed papers so a new user can rate them (issue form `bootstrap-feedback`)."""
    from .ranking.profile import build_vectors
    V = build_vectors(settings, [], date.today())
    cands = arxiv.recent(settings.sources.arxiv_categories, 7, max_results=400) + hf_daily.trending(limit=30)
    cands += essential_candidates(settings)
    cands = dedup(cands)
    scored = sorted(score_all(settings, cands, V), key=lambda s: s.sim_profile, reverse=True)
    chosen: list = []
    for s in scored:
        if all(float(s.vec @ c.vec) < 0.7 for c in chosen):
            chosen.append(s)
        if len(chosen) >= 20:
            break
    print("Rate these to seed your profile (copy into the bootstrap-feedback issue):\n")
    for s in chosen:
        print(f"- [ ] 👍  [ ] 👎  {s.paper.title}  ({s.paper.url})")
    return 0
