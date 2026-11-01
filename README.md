# scout

**A daily research-reading practice, not another paper feed.**

Every morning scout picks 1–3 papers for you. After you read one, it asks you two things: *what did you understand* and *what gaps did you find*. Your answer becomes a note in a notebook you can browse forever, and your **gaps decide what you read tomorrow**.

- 🗓 **1 deep read + up to 2 skims a day.** No backlog: unread picks expire, nothing piles up.
- ✍️ **Two boxes after reading.** Understood / gaps. That's the whole practice.
- 🧭 **Gap-driven path.** Yesterday's "I don't get X" becomes today's search. The `path` page shows the chain.
- 🔎 **Three lanes, no LLM-from-memory picks.** Your niche (fresh arXiv + gap searches), the citation neighbourhood of what you've read, and field-wide essentials/trending. Candidates always come from real sources; the LLM only ranks and explains.
- 📌 **Bring your own.** Log papers you read elsewhere, queue papers you want to read eventually.
- 🆓 **Runs on GitHub, nothing on your laptop.** Actions do the work, Pages hosts the notebook, Issue Forms are the reflection form. Notes are plain markdown in the repo.

Why this exists: Scholar Inbox, arXiv digests and friends all stop at "here are papers you might like". None make you write, none keep a notebook, and none use what you wrote to choose the next paper. Reading without writing doesn't stick, and asking an LLM for reading lists gives everyone the same twenty famous papers.

## Setup (≈30 min, free)

See [docs/setup.md](docs/setup.md). Short version:

1. **Use this template** → private repo.
2. Edit `config/profile.md` (who you are, what you want to read) and glance at `config/settings.yaml`.
3. Add secrets: one LLM key (`ANTHROPIC_API_KEY`, or free-tier `GEMINI_API_KEY` / `GROQ_API_KEY`), optional `S2_API_KEY`.
4. Settings → Actions → *Read and write permissions*. Settings → Pages → source *GitHub Actions*.
5. Run the **daily** workflow once. Open your Pages URL.

## How a day goes

```
07:00  daily workflow → data/today.json → site rebuilt
       you open the site, read the deep pick
       click "i read this" → GitHub issue form, two boxes, submit
       ingest workflow → notes/2026/11/<id>.md, issue closed, site rebuilt
07:00  next day: your gaps → search queries → new picks, linked back to your note
```

## Local use

```bash
uv venv && uv pip install -e ".[all,dev]"
scout run-daily --dry-run --no-llm     # see picks without writing
scout build-site && python -m http.server -d site_build
pytest
```

## Layout

```
config/profile.md, settings.yaml   the only files you need to touch
src/scout/sources/                  arxiv, semantic_scholar, hf_daily, openreview (+ dedup)
src/scout/ranking/                  embed, profile, score, select
src/scout/llm/                      anthropic | gemini | groq, with fallback chain
src/scout/notes/                    note format, issue-form ingestion, stats
src/scout/site/                     static notebook (today, notes, path, later, stats)
.github/workflows/                  daily, ingest-issue, site, bootstrap, tests
.github/ISSUE_TEMPLATE/             read, log-paper, want, skip, bootstrap-feedback
notes/YYYY/MM/<id>.md               your notebook, plain markdown
data/                               state.json, today.json, want.yaml (committed by Actions)
```

## Sources and the "same papers as everyone" problem

| lane | where candidates come from |
|---|---|
| niche | new arXiv listings in your categories; arXiv + Semantic Scholar searches built from your gap notes |
| neighbourhood | Semantic Scholar references, citations and recommendations seeded by your last reads; authors you rated highly |
| field | Hugging Face Daily Papers upvotes; highly-cited classics on your topics (the `essential` slot); recent conference papers via Semantic Scholar's venue filter |

The niche lane **penalises** papers that are already trending or heavily cited, so it surfaces things the feed-readers won't. Google Scholar is deliberately not a source (no API, scraping violates its terms). OpenReview's API now requires a login token; set `OPENREVIEW_TOKEN` if you have one.

## License

MIT.
