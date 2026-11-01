# Setting up scout

Do these in order. ~30 minutes. Everything is free.

## 1. Make your copy

1. Click **Use this template → Create a new repository**. Make it **private** (your notes are yours).
2. Clone it or just edit on GitHub with the pencil icon.

## 2. Tell it who you are

- `config/profile.md`: a few paragraphs on what you work on and what you want to read. Be specific; this becomes your profile vector.
- `config/settings.yaml`: timezone and hour, papers per day, arXiv categories, topic weights. Defaults are fine to start.

Delete `notes/2026/10/2510.00001.md` (the sample note) or leave it as an example of the format.

## 3. Keys

Settings → Secrets and variables → Actions → **New repository secret**:

| name | needed? | where |
|---|---|---|
| `ANTHROPIC_API_KEY` | one LLM key is enough | console.anthropic.com (a few cents a day) |
| `GEMINI_API_KEY` | free alternative | aistudio.google.com/apikey |
| `GROQ_API_KEY` | free fallback | console.groq.com/keys |
| `S2_API_KEY` | optional but recommended | semanticscholar.org/product/api (approval takes days; without it the neighbourhood lane is rate-limited and sometimes thin) |
| `OPENREVIEW_TOKEN` | optional | only if you want OpenReview as a direct source |

With no LLM key scout still runs; picks just show the abstract instead of a tailored "why".

## 4. Let Actions write

Settings → Actions → General → **Workflow permissions → Read and write permissions** → Save.

## 5. Turn on Pages

Settings → Pages → Build and deployment → **Source: GitHub Actions**.

## 6. Seed your taste (optional, 5 min)

Actions → **bootstrap** → Run workflow. It opens an issue with ~20 papers. Edit the issue, tick 👍 or 👎 on each line, then add the label `scout:bootstrap`. The ingest workflow records your votes.

## 7. First run

Actions → **daily** → Run workflow (leave *force* on). When it's green, Actions → **site** runs on its own and your Pages URL (Settings → Pages) shows today's picks.

From now on it runs every morning at the hour in `settings.yaml`. GitHub's scheduler can be 5–30 minutes late; that's normal.

## Daily use

- **Read** the deep pick (and skim the skims if you like).
- Click **i read this** → fill the two boxes → Submit. The issue closes itself within a minute and your note appears on the site.
- **later** puts a pick in your want queue; **skip** makes it go away for good.
- Footer links: **i read something else** (log any paper), **i want to read this eventually** (queue any paper).
- Missed a day? Nothing happens. Tomorrow brings fresh picks. There is no backlog on purpose.

## Changing things

- Interests: edit `config/profile.md` / `config/settings.yaml` on GitHub. Next run uses them.
- Want queue order: edit `data/want.yaml`.
- A note: every note page has *edit this note on github*.
- The LLM stopped working: free-tier model names change. Update `llm.models` in `settings.yaml`.
- Push rejected locally: Actions commit to the repo; `git pull --rebase` first.
