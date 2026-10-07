from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
PRICES_FILE = PROCESSED_DIR / "prices_daily.csv"
EVENTS_FILE = PROCESSED_DIR / "macro_events.csv"
EVENT_SOURCES_FILE = PROCESSED_DIR / "macro_event_sources.csv"
POOL_SNAPSHOTS_FILE = PROCESSED_DIR / "curve_3pool_balances.csv"
