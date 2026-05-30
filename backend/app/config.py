"""Environment wiring. Secrets and infra endpoints only.

All *tweakable* pipeline parameters live in the editable config doc
(see app/models/pipeline_config.py), NOT here. This file holds only the
values that must come from the deployment environment: API keys and the
R2 connection details.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- Provider API keys (already present in Render env) ---
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    # Accept the legacy short name from the shared env group.
    elevenlabs_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ELEVENLABS_API_KEY", "ELEVENLABS"),
    )
    fal_key: str = Field(default="", alias="FAL_KEY")
    suno_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUNO_API_KEY", "SUNOAPI"),
    )
    suno_api_base: str = Field(
        default="https://api.sunoapi.org", alias="SUNO_API_BASE"
    )
    elevenlabs_api_base: str = Field(
        default="https://api.elevenlabs.io", alias="ELEVENLABS_API_BASE"
    )

    # --- Gemini via Vertex AI (fallback when no GEMINI_API_KEY) ---
    # The shared env group carries a service-account JSON; use it to call
    # Gemini through Vertex when the AI-Studio key is not provided.
    google_application_credentials_json: str = Field(
        default="", alias="GOOGLE_APPLICATION_CREDENTIALS_JSON"
    )
    gcp_project: str = Field(default="", alias="GCP_PROJECT")
    gcp_location: str = Field(default="us-central1", alias="GCP_LOCATION")

    # --- Cloudflare R2 (S3-compatible) ---
    r2_account_id: str = Field(default="", alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", alias="R2_SECRET_ACCESS_KEY")
    r2_bucket: str = Field(
        default="",
        validation_alias=AliasChoices("R2_BUCKET", "R2_BUCKET_NAME"),
    )
    # Optional explicit endpoint; if blank we derive it from the account id.
    r2_endpoint: str = Field(default="", alias="R2_ENDPOINT")
    # Public base URL for serving artifacts (R2 public bucket / custom domain).
    r2_public_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("R2_PUBLIC_BASE_URL", "R2_PUBLIC_URL"),
    )

    # --- Local fallback (used only when R2 is not configured, e.g. dev) ---
    local_storage_dir: str = Field(default="./.artifacts", alias="LOCAL_STORAGE_DIR")

    @property
    def r2_endpoint_url(self) -> str:
        if self.r2_endpoint:
            return self.r2_endpoint
        if self.r2_account_id:
            return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
        return ""

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket
            and self.r2_endpoint_url
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
