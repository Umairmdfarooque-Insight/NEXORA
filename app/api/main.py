"""Nexora orchestration API. Start: uvicorn app.api.main:app --reload --port 8000

No authentication yet (T-105), so run it locally only.
"""

import subprocess

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import fabric, runs
from app.api.errors import register_error_handlers
from app.api.schemas import Health
from app.config import APP_NAME, PROJECT_ROOT

RAYFIN_ORIGIN = "http://localhost:3000"


def _version() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "0.0.0"
    sha = out.stdout.strip()
    return sha if out.returncode == 0 and sha else "0.0.0"


VERSION = _version()

app = FastAPI(title=f"{APP_NAME} API", version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[RAYFIN_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)
app.include_router(runs.router)
app.include_router(fabric.router)


@app.get("/health", response_model=Health, tags=["health"])
def health() -> Health:
    return Health(status="ok", app=APP_NAME, version=VERSION)
