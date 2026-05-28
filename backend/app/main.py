from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import config_routes, job_routes
from app.config import get_settings

app = FastAPI(title="pivotnews-videos", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config_routes.router)
app.include_router(job_routes.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "storage": "r2" if s.r2_configured else "local",
    }
