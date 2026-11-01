# PRD + Build Plan: Daily Research Reading Practice (`scout`)

## Context

You want to read AI/ML papers every day instead of just collecting them, and to keep a record of what you understood and what you didn't. Existing tools (Scholar Inbox, SmartXiv, ArxivDigest, zotero-arxiv-daily, the sideproject.ai Notion guide saved in `reference/ai-paper-digest-notion.md`) all stop at "here are papers you might like". None force a reflection, none keep a browsable notebook, and none use what you wrote to pick tomorrow's paper. That loop is the product.

Two audiences, one codebase:
1. **You**: daily use, seeded with LLMs/agents + CV/multimodal.
2. **Open-source template users**: fork, add keys, edit one profile file, done. Same setup burden as the Notion guide (~45 min, nothing runs locally).

Decisions already made:
- **Delivery**: GitHub-only. Actions run the pipeline, GitHub Pages serves the notebook, GitHub Issue Forms are the reflection form. No server, no laptop.
- **LLM**: Claude if `ANTHROPIC_API_KEY` is set, else free tier (Gemini, then Groq). Provider pluggable.
- **Load**: Mixed. 1 deep read + up to 2 skims per day. Configurable 1–3.
- **Notes**: plain markdown in the repo, one file per paper. Portable, no lock-in.

---

## Part 1: PRD

### Problem
Reading papers via LLM recommendations gives everyone the same famous papers, and reading without writing produces no retained knowledge. Need: a daily, personal, gap-driven reading path with forced reflection and a permanent record.

### Goals
- Deliver 1–3 papers every morning, each with "why you" and "what you'll walk away with".
- After reading, capture two things: **what I understood** and **what gaps I found**. Nothing else required.
- Keep every note in a searchable notebook (static site + markdown).
- Use the gaps text to drive the next day's picks (not just thumbs up/down).
- Mix three lanes: your niche, the citation neighbourhood of what you've read, and field-wide essentials/trending.
- Avoid the "same papers as everyone" problem: candidates come from deterministic sources, never from the LLM's memory; popularity is downweighted in the niche lane.
- Forkable template: fork → 1–2 secrets → edit `config/profile.md` → enable Pages → first run.

### Non-goals (v1)
- Hosted multi-user service, accounts, billing.
- In-app PDF reader or annotation.
- Mobile app. (Pages site is responsive; that is enough.)
- Google Scholar scraping (ToS). Not a source.
- Spaced repetition / quizzes. Possible v2.

### Users
- **Primary**: you (daily).
- **Secondary**: ML practitioners/students who want a reading habit and already use GitHub.

### Daily flow (user's view)
1. Morning: Pages site home shows **Today** — 1 deep pick + up to 2 skims. Each card: title, authors, venue/date, links (abstract, PDF), lane tag (`niche` / `neighbourhood` / `field`), depth tag (`deep` / `skim`), "Why read it" (2–3 sentences tied to profile **and to your recent gaps**), "What you'll walk away with".
2. Read the paper.
3. Click **"I read this"** → opens a pre-filled GitHub Issue Form: two textareas (`Understood`, `Gaps`), optional 1–5 rating, optional tags. Submit.
4. Action fires on issue creation: writes `notes/YYYY/MM/<arxiv-id>.md`, closes the issue, updates the profile state, rebuilds the site.
5. Next morning's run reads the latest gaps and queries for them.
Also on each card: **Skip** (opens issue with label `skip`, optional reason) and **Save for later** (`later` label). Both are one click.

**Bring your own paper.** Two more one-click entry points on the site header:
- **"I read something else"** → Issue Form `log-paper.yml`: paper URL or arXiv id/DOI + the same two boxes (`Understood`, `Gaps`) + optional rating. Ingest resolves metadata via arXiv/S2, writes the note exactly like a system pick (lane `own`), marks it seen, and its gaps feed tomorrow's run like any other note.
- **"I want to read this eventually"** → Issue Form `want.yml`: URL/id + optional "why" + optional "by when". Goes into a **want queue**. The daily selector serves one want-queue paper in the deep slot at most every N days (default 3, configurable), oldest-first unless a "by when" is near. Want-queue papers skip the popularity penalty and the relevance floor; you asked for them. The `/later` page shows the queue with reorder/remove via issue comments or by editing `data/want.yaml` directly.

**No backlog.** Picks are for *today* only. If you don't read a pick, the next morning's run replaces it; nothing accumulates and nothing nags. Unread picks are recorded as `missed` (not `seen`), so they can be re-picked later if they stay relevant, but they are never carried forward automatically. A skipped day is just a skipped day: the streak counter resets, the Today page shows fresh picks, and the `/path` view shows a gap in the timeline rather than a pile. Only the want queue persists, because you put those there on purpose.

### Notebook (Pages site)
- `/` Today.
- `/notes` all notes, newest first, full-text search (client-side, Lunr/Pagefind), filter by lane/tag/rating.
- `/paper/<id>` the note page: paper metadata, your two boxes, "led to" links (papers later picked because of this note's gaps).
- `/path` a timeline view: what you read, what gap it raised, what that gap led to. This is the thing nobody else has.
- `/later` saved list. `/stats` counts, lanes, topic drift.

### Recommendation engine
**Candidate sources (all deterministic, all free):**
| Lane | Source | Notes |
|---|---|---|
| niche | arXiv API, categories from `settings.yaml` (default cs.LG, cs.CL, cs.AI, cs.CV, cs.MM, stat.ML) | last 2 days of listings |
| niche | arXiv + Semantic Scholar search using **queries generated from your gaps text** | the gap loop |
| neighbourhood | Semantic Scholar: references, citations, and `/recommendations` for your last N read papers | 1-hop citation walk |
| neighbourhood | Semantic Scholar author search for authors of papers you rated ≥4 | author following |
| field | Hugging Face Daily Papers (upvotes) | trending |
| field | Semantic Scholar highly-cited in your categories, any year | essentials / classics |
| field | OpenReview accepted lists for configurable venues (ICLR, NeurIPS, ICML, ACL, CVPR...) during their windows | conference awareness |

**Scoring:**
- Embed title+abstract with a small CPU model (sentence-transformers `allenai-specter2` or `all-MiniLM-L6-v2`; cached in Actions).
- Profile vector = embed(`profile.md`) + mean(read papers weighted by rating) − disliked/skipped.
- Gap vector = embed(last 7 days of gap text), weighted recency.
- `niche_score = sim(profile) * topic_weight + 0.5 * sim(gaps) − popularity_penalty` (penalty if HF-trending or citations > threshold, so the niche lane surfaces non-obvious work).
- `neighbourhood_score = citation-walk proximity * sim(profile)`.
- `field_score = trending/citation velocity with relevance floor`.
- Diversity: max cosine between the day's picks < 0.85.
- Never repeat a seen paper (seen = read, skipped, logged-own, in want queue). `missed` picks are eligible again after 14 days.
- Want-queue slot: at most one per N days in the deep slot, bypasses penalty and floor.
- Depth assignment: highest-scoring niche or neighbourhood pick is `deep`; others `skim`. Essentials are always `deep` and replace the deep slot every Nth day (default 4).

**LLM usage (small, few calls/day):**
- Turn gap text → 2–3 search queries + keywords.
- Write "Why read it" / "What you'll walk away with" per pick, with profile + recent gaps as context.
- Pick essentials candidates from a shortlist (shortlist comes from S2, not LLM memory).
- Fallback if LLM fails: ship title + abstract snippet, still run.

### Configuration (template users touch only these)
- `config/profile.md`: free-text description of who you are and what you care about.
- `config/settings.yaml`: papers per day, deep/skim mix, arXiv categories, topic weights, venues to watch, essentials cadence, timezone + hour, LLM provider order.
- Secrets: `ANTHROPIC_API_KEY` (optional), `GEMINI_API_KEY` (optional), `GROQ_API_KEY` (optional), `S2_API_KEY` (optional). At least one LLM key required; pipeline degrades gracefully without it.

### Data (all in repo, committed by Actions)
- `data/state.sqlite` or JSON: seen papers, embeddings cache, profile/gap vectors, offsets.
- `data/today.json`: current picks.
- `notes/YYYY/MM/<id>.md` with YAML front-matter (title, id, links, lane, depth, rating, tags, date, led_to[]).
- `site/` generated output (or built on the fly by the Pages workflow; do not commit build output).

### Success metrics (personal)
- Streak: days with ≥1 note.
- Gap closure: % of gaps that produced a later pick that got read.
- Notes written per week; skips per week (if skips > reads, ranking is off).

### Open-source packaging
- MIT license, `README` leading with the reflection loop and the `/path` view, **not** "daily arXiv digest".
- "Use this template" button; a `bootstrap` workflow that sends ~20 seed papers for thumbs-up/down (issue with checkboxes).
- `CONTRIBUTING.md`, issue templates, a `docs/` folder with the setup guide (modelled on the Notion guide's step list).
- `--dry-run` everywhere; tests for dedup, scoring, note parsing.

### Risks
- Semantic Scholar rate limits without a key: backoff + cache; degrade neighbourhood lane.
- Free-tier model names churn: provider table in `settings.yaml`, documented.
- GitHub Issue Forms require the repo to be public **or** the user to be logged in; fine for personal private repos.
- Actions commits racing: `concurrency` groups, pull-rebase before push.
- Embedding model download time: cache via `actions/cache`.

---

## Part 2: Build plan

### Repo layout
```
scout/
  config/profile.md, settings.yaml
  src/scout/
    sources/   arxiv.py, semantic_scholar.py, hf_daily.py, openreview.py
    ranking/   embed.py, profile.py, score.py, select.py
    llm/       base.py, anthropic.py, gemini.py, groq.py, router.py
    notes/     parse.py, write.py, ingest_issue.py
    site/      build.py (templates/, static/)
    cli.py     (run-daily, ingest-issue, build-site, bootstrap, stats; all with --dry-run)
    storage.py
  notes/, data/
  .github/
    workflows/ daily.yml, ingest-issue.yml, build-site.yml, bootstrap.yml
    ISSUE_TEMPLATE/ read.yml, skip.yml, later.yml, log-paper.yml, want.yml, bootstrap-feedback.yml
  tests/
  docs/setup.md, README.md, LICENSE, pyproject.toml
```

### Milestones (each ends runnable with `--dry-run`)
1. **Skeleton + config + storage.** `pyproject`, settings loader, storage layer, CLI stub. Seed `profile.md` with LLMs/agents + CV/multimodal.
2. **Sources + dedup.** arXiv, S2, HF, OpenReview clients with retries/backoff; normalise to one `Paper` model; dedup on arXiv id / DOI / normalised title. `run-daily --dry-run` prints candidate counts per lane.
3. **Embeddings + scoring + selection.** Profile/gap vectors, lane scores, popularity penalty, diversity, depth assignment. Dry run prints the 3 picks with scores.
4. **LLM layer.** Router (Anthropic → Gemini → Groq → none), gap→queries, explanations, essentials shortlist choice. Graceful fallback.
5. **Notes + issue ingestion.** Issue Form templates (read, skip, later, log-paper, want); `ingest-issue` parses the issue body into a note file or want-queue entry, resolves metadata for user-supplied URLs/ids, closes the issue, updates seen/missed/profile/gap state, records `led_to` links when a later pick traces to a gap. Daily run marks yesterday's unread picks `missed` before selecting (no backlog).
6. **Site.** Static builder (Jinja2 + Pagefind or Lunr): Today, Notes, Paper, Path, Later, Stats. Mobile-friendly. Minimal styling.
7. **Workflows.** `daily.yml` (cron in your timezone, DST-safe hourly window check, `workflow_dispatch` with `dry_run`), `ingest-issue.yml` (on `issues: opened` with label), `build-site.yml` (on push to `notes/`/`data/`, deploy to Pages), `bootstrap.yml`. Concurrency groups, write permissions, `actions/cache` for the model.
8. **Template polish.** README, `docs/setup.md` step list, `CONTRIBUTING.md`, license, tests, `bootstrap` seeding flow, "Use this template" ready. Run the whole setup as a fresh fork to verify the 45-minute claim.

### Verification
- `pytest` for dedup, scoring, note parsing, issue-body parsing.
- `scout run-daily --dry-run` locally prints 3 picks with lane/depth and explanations.
- Open a test "I read this" issue on the repo → note file appears, issue closes, site rebuilds, next dry run shows a gap-derived query in its log.
- Open a "log paper" issue with a raw arXiv URL → note appears under lane `own` with resolved title/authors.
- Open a "want" issue → appears on `/later`; a dry run with `--force-want` shows it in the deep slot.
- Run `run-daily` twice without reading → second run's picks differ, first run's picks are in `missed`, nothing on Today older than today.
- Fork into a throwaway account, follow `docs/setup.md` only, time it, confirm first digest and first note.

### Not building in v1 (explicitly)
Local FastAPI app (option 2), hosted version, PDF reader, spaced repetition. The pipeline is a plain package so the local app can wrap it later.
