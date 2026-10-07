from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.events import router as events_router
from backend.app.api.experiments import router as experiments_router
from backend.app.config import FRONTEND_DIR
from backend.app.public_demo import PUBLIC_DEMO, PublicDemoLimits

app = FastAPI(
    title="Stablecoin Stress Lab API",
    description="Historical stablecoin price replay and conditional Curve 3pool swap estimates.",
    version="0.1.0",
)
app.add_middleware(PublicDemoLimits)
app.include_router(events_router)
app.include_router(experiments_router)
app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/frontend/")


@app.get("/api/public-config")
def public_config():
    return {"public_demo": PUBLIC_DEMO, "uploads_enabled": not PUBLIC_DEMO}


if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
