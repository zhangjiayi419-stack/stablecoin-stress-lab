from backend.app.config import POOL_SNAPSHOTS_FILE
from backend.app.data_sources.csv_import import read_csv, write_csv_atomic

POOL_FIELDS = ["timestamp", "dai_pool", "usdc_pool", "usdt_pool", "amp", "fee_rate", "source", "method"]


def load_pool_snapshots() -> list[dict[str, str]]:
    if not POOL_SNAPSHOTS_FILE.exists():
        return []
    rows = read_csv(POOL_SNAPSHOTS_FILE, POOL_FIELDS)
    return sorted(rows, key=lambda row: row["timestamp"])


def save_pool_snapshots(rows: list[dict[str, object]]) -> None:
    write_csv_atomic(POOL_SNAPSHOTS_FILE, POOL_FIELDS, rows)
