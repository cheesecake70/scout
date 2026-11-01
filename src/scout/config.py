from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def repo_root() -> Path:
    env = os.environ.get("SCOUT_ROOT")
    if env:
        return Path(env)
    here = Path.cwd()
    for p in [here, *here.parents]:
        if (p / "config" / "settings.yaml").exists():
            return p
    return here


class Schedule(BaseModel):
    timezone: str = "UTC"
    hour: int = 7


class Load(BaseModel):
    papers_per_day: int = 3
    deep_picks: int = 1
    essentials_every_n_days: int = 4
    want_every_n_days: int = 3
    missed_cooldown_days: int = 14


class Sources(BaseModel):
    arxiv_categories: list[str] = ["cs.LG", "cs.CL", "cs.AI"]
    arxiv_lookback_days: int = 2
    neighbourhood_recent_reads: int = 5
    author_follow_min_rating: int = 4
    venues: list[dict] = []
    openreview_venues: list[str] = []
    hf_daily: bool = True


class Ranking(BaseModel):
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    gap_weight: float = 0.5
    popularity_penalty: float = 0.15
    popularity_citation_threshold: int = 200
    diversity_max_cosine: float = 0.85
    relevance_floor: float = 0.25


class LLM(BaseModel):
    provider_order: list[str] = ["anthropic", "gemini", "groq"]
    models: dict[str, str] = {}


class Site(BaseModel):
    title: str = "scout"
    base_url: str = ""


class Settings(BaseModel):
    schedule: Schedule = Field(default_factory=Schedule)
    load: Load = Field(default_factory=Load)
    sources: Sources = Field(default_factory=Sources)
    topics: dict[str, float] = {}
    ranking: Ranking = Field(default_factory=Ranking)
    llm: LLM = Field(default_factory=LLM)
    site: Site = Field(default_factory=Site)

    root: Path = Field(default_factory=repo_root, exclude=True)

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def notes_dir(self) -> Path:
        return self.root / "notes"

    @property
    def profile_text(self) -> str:
        p = self.config_dir / "profile.md"
        return p.read_text() if p.exists() else ""


def load_settings(root: Path | None = None) -> Settings:
    root = root or repo_root()
    path = root / "config" / "settings.yaml"
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text()) or {}
    s = Settings(**raw)
    s.root = root
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.notes_dir.mkdir(parents=True, exist_ok=True)
    return s
