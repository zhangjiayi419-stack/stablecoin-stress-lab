from backend.app.config import EVENTS_FILE, EVENT_SOURCES_FILE, PRICES_FILE
from backend.app.data_sources.csv_import import read_csv

PRICE_COLUMNS = {
    "date_utc", "asset", "close_usd", "mean_usd", "min_sampled_usd",
    "max_sampled_usd", "hourly_observations_count", "daily_close_change_pct",
    "source", "method",
}
EVENT_COLUMNS = {
    "event_id", "start_utc", "end_utc", "category", "tokens", "summary",
    "price_series_note", "interpretation_caveat",
}


def load_prices() -> list[dict[str, str]]:
    return read_csv(PRICES_FILE, PRICE_COLUMNS)


def load_events() -> list[dict[str, str]]:
    return read_csv(EVENTS_FILE, EVENT_COLUMNS)


def load_event_sources() -> list[dict[str, str]]:
    return read_csv(EVENT_SOURCES_FILE, {"event_id", "source_url"})
