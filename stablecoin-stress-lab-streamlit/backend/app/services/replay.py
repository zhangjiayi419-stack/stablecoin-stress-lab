from datetime import date

from backend.app.data_sources.curve_pool import load_pool_snapshots
from backend.app.data_sources.prices import load_event_sources, load_events, load_prices


def load_history() -> dict:
    return {"prices": load_prices(), "events": load_events(), "sources": load_event_sources()}


def load_replay_events() -> list[dict[str, str]]:
    return load_events()


def load_pool_state() -> list[dict[str, str]]:
    return load_pool_snapshots()


def pool_snapshot_for_date(day: date) -> dict[str, str] | None:
    snapshots = [row for row in load_pool_snapshots() if row["timestamp"][:10] == day.isoformat()]
    return snapshots[-1] if snapshots else None
