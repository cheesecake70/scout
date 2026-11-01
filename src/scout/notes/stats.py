from __future__ import annotations

from collections import Counter

from ..config import Settings
from ..storage import Storage
from .parse import load_notes


def print_stats(settings: Settings) -> int:
    notes = load_notes(settings)
    st = Storage(settings).state
    print(f"papers read: {len(notes)}")
    print(f"with gaps written: {sum(1 for n in notes if n.gaps.strip())}")
    print(f"gaps that led to a later read: {sum(1 for n in notes if n.led_to)}")
    print(f"lanes: {dict(Counter(n.lane for n in notes))}")
    print(f"skips: {len(st.get('skips', {}))}, missed: {len(st.get('missed', {}))}, run days: {len(st.get('run_days', []))}")
    return 0
