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
        # Booleans only — never the values. Lets us diagnose missing env
        # mappings without leaking secrets.
        "env_seen": {
            "GEMINI_API_KEY": bool(s.gemini_api_key),
            "GOOGLE_APPLICATION_CREDENTIALS_JSON": bool(
                s.google_application_credentials_json
            ),
            "ELEVENLABS": bool(s.elevenlabs_api_key),
            "FAL_KEY": bool(s.fal_key),
            "SUNO": bool(s.suno_api_key),
            "R2_ACCOUNT_ID": bool(s.r2_account_id),
            "R2_ACCESS_KEY_ID": bool(s.r2_access_key_id),
            "R2_SECRET_ACCESS_KEY": bool(s.r2_secret_access_key),
            "R2_BUCKET": bool(s.r2_bucket),
            "R2_PUBLIC_URL": bool(s.r2_public_base_url),
        },
    }
