from fastapi import APIRouter, HTTPException

from backend.app.config import POOL_SNAPSHOTS_FILE
from backend.app.data_sources.curve_pool import load_pool_snapshots, save_pool_snapshots
from backend.app.domain.schemas import HistoryResponse, PoolSnapshot, PoolSnapshotImport
from backend.app.services.replay import load_history, load_replay_events, load_pool_state

router = APIRouter(prefix="/api", tags=["Replay data"])


@router.get("/health")
def health() -> dict:
    try:
        snapshot_count = len(load_pool_snapshots())
    except (FileNotFoundError, ValueError):
        snapshot_count = 0
    return {"ok": True, "pool_snapshots": snapshot_count, "pool_data_available": POOL_SNAPSHOTS_FILE.exists()}


@router.get("/history", response_model=HistoryResponse)
def history() -> dict:
    try:
        return load_history()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/events")
def events() -> list[dict[str, str]]:
    try:
        return load_replay_events()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/pool-snapshots")
def pool_snapshots() -> dict:
    try:
        snapshots = load_pool_state()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "snapshots": snapshots,
        "available": POOL_SNAPSHOTS_FILE.exists(),
        "required_fields": list(PoolSnapshot.model_fields),
    }


@router.post("/pool-snapshots", status_code=201)
def import_pool_snapshots(payload: PoolSnapshotImport) -> dict:
    incoming = [row.model_dump(mode="json") for row in payload.snapshots]
    incoming_timestamps = [row["timestamp"] for row in incoming]
    if len(set(incoming_timestamps)) != len(incoming_timestamps):
        raise HTTPException(status_code=422, detail="Duplicate timestamps in the uploaded snapshots are not allowed")
    existing = load_pool_snapshots()
    merged = {row["timestamp"]: row for row in existing}
    merged.update({row["timestamp"]: row for row in incoming})
    snapshots = sorted(merged.values(), key=lambda row: row["timestamp"])
    save_pool_snapshots(snapshots)
    return {"saved": len(incoming), "total": len(snapshots), "path": "data/processed/curve_3pool_balances.csv"}


@router.get('/macro-context-candidates')
def macro_context_candidates():
    import json
    from backend.app.config import PROCESSED_DIR
    path = PROCESSED_DIR / 'macro_context_candidates.json'
    return {'items':json.loads(path.read_text()) if path.exists() else [],
            'label':'UNREVIEWED COLLECTED SOURCE MATERIAL · NOT VALIDATED EVENTS'}
