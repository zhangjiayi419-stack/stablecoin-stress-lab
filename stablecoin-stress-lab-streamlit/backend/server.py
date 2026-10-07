"""Compatibility launcher. Prefer `python3 -m backend.app.main`."""

from backend.app.main import app

if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
