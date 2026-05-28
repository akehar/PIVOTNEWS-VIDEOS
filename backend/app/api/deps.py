from __future__ import annotations

from app.storage.factory import get_storage
from app.stores.config_store import ConfigStore
from app.stores.job_store import JobStore


def get_config_store() -> ConfigStore:
    return ConfigStore(get_storage())


def get_job_store() -> JobStore:
    return JobStore(get_storage())
