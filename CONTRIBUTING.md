# Contributing

Issues and PRs welcome. Keep the practice small: the point is two boxes after reading, not a feature-rich reader.

```bash
uv venv && uv pip install -e ".[all,dev]"
pytest
ruff check src tests
scout run-daily --dry-run --no-llm
```

Good first contributions: a new candidate source (follow `src/scout/sources/hf_daily.py`), a better essentials shortlist, a `missed`-aware ranking tweak, or site polish. Sources must be free, have a public API, and not violate the provider's terms (Google Scholar is out).
