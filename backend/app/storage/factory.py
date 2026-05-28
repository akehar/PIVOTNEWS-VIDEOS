from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.storage.base import Storage
from app.storage.local import LocalStorage
from app.storage.r2 import R2Storage


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.r2_configured:
        return R2Storage(
            endpoint_url=s.r2_endpoint_url,
            access_key_id=s.r2_access_key_id,
            secret_access_key=s.r2_secret_access_key,
            bucket=s.r2_bucket,
            public_base_url=s.r2_public_base_url,
        )
    return LocalStorage(s.local_storage_dir)
