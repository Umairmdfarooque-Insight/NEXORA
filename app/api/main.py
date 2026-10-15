"""Nexora orchestration API. Start: uvicorn app.api.main:app --reload --port 8000

Every endpoint except /health needs an Entra bearer token (T-105).
"""

import logging
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import fabric, runs
from app.api.errors import register_error_handlers
from app.api.schemas import Health
from app.compiler.critical_terms import load_critical_terms
from app.config import APP_NAME, PROJECT_ROOT
from app.workflow.roles import load_roles

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

# Stage graphs log their node path at INFO. Only the app's own loggers are switched on, so
# third-party libraries stay quiet.
_app_logger = logging.getLogger("app")
_app_logger.setLevel(logging.INFO)
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    _app_logger.addHandler(_handler)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_critical_terms()  # a missing or invalid config/critical_terms.yaml stops the API here
    load_roles()  # so does config/roles.yaml
    yield


app = FastAPI(title=f"{APP_NAME} API", version=VERSION, lifespan=lifespan)
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
