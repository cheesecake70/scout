"""All persistent state lives in the repo so GitHub Actions can commit it.

data/state.json   seen / missed / served-day counters
data/today.json   current picks
data/want.yaml    the want queue (hand-editable)
data/cache/       embeddings and API caches (gitignored)
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import yaml

from .config import Settings
from .models import Today, WantItem


class Storage:
    def __init__(self, settings: Settings):
        self.s = settings
        self.state_path = settings.data_dir / "state.json"
        self.today_path = settings.data_dir / "today.json"
        self.want_path = settings.data_dir / "want.yaml"
        self.cache_dir = settings.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, Any] | None = None

    # ---- state -------------------------------------------------------
    @property
    def state(self) -> dict[str, Any]:
        if self._state is None:
            if self.state_path.exists():
                self._state = json.loads(self.state_path.read_text())
            else:
                self._state = {}
            self._state.setdefault("seen", {})      # id -> {status, date}
            self._state.setdefault("missed", {})    # id -> date
            self._state.setdefault("last_essential", None)
            self._state.setdefault("last_want", None)
            self._state.setdefault("run_days", [])
        return self._state

    def save_state(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=2, sort_keys=True, default=str) + "\n")

    def mark_seen(self, paper_id: str, status: str, on: date | None = None) -> None:
        self.state["seen"][paper_id] = {"status": status, "date": (on or date.today()).isoformat()}
        self.state["missed"].pop(paper_id, None)

    def mark_missed(self, paper_id: str, on: date | None = None) -> None:
        if paper_id in self.state["seen"]:
            return
        self.state["missed"][paper_id] = (on or date.today()).isoformat()

    def is_excluded(self, paper_id: str, today: date, cooldown_days: int) -> bool:
        if paper_id in self.state["seen"]:
            return True
        m = self.state["missed"].get(paper_id)
        if m:
            missed_on = date.fromisoformat(m)
            return (today - missed_on).days < cooldown_days
        return False

    # ---- today -------------------------------------------------------
    def load_today(self) -> Today | None:
        if not self.today_path.exists():
            return None
        return Today.model_validate_json(self.today_path.read_text())

    def save_today(self, today: Today) -> None:
        self.today_path.write_text(today.model_dump_json(indent=2) + "\n")

    # ---- want queue --------------------------------------------------
    def load_want(self) -> list[WantItem]:
        if not self.want_path.exists():
            return []
        raw = yaml.safe_load(self.want_path.read_text()) or []
        return [WantItem(**x) for x in raw]

    def save_want(self, items: list[WantItem]) -> None:
        data = [json.loads(i.model_dump_json()) for i in items]
        self.want_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    # ---- cache -------------------------------------------------------
    def cache_get(self, key: str) -> Any | None:
        p = self.cache_dir / f"{key}.json"
        if p.exists():
            return json.loads(p.read_text())
        return None

    def cache_set(self, key: str, value: Any) -> None:
        (self.cache_dir / f"{key}.json").write_text(json.dumps(value, default=str))


def now() -> datetime:
    return datetime.now().astimezone()
