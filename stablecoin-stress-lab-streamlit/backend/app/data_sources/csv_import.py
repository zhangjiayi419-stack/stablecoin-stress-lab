"""CSV readers and atomic writers used by the local research prototype."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from typing import Iterable, Mapping


def read_csv(path: Path, required: Iterable[str] = ()) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required dataset not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        missing = sorted(set(required) - set(headers))
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(missing)}")
        rows = []
        for line, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"{path.name}, row {line}: extra values beyond the header")
            rows.append({key: (value or "").strip() for key, value in row.items()})
        return rows


def write_csv_atomic(path: Path, fields: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    """Replace a data file atomically so a failed import cannot leave a partial CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
