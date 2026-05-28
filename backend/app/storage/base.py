from __future__ import annotations

import json
from typing import Protocol


class Storage(Protocol):
    """Artifact store. Keys are forward-slash paths, e.g. jobs/<id>/job.json."""

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str: ...

    def get_bytes(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def url(self, key: str) -> str: ...

    def list_prefix(self, prefix: str) -> list[str]: ...


def put_json(store: Storage, key: str, obj: object) -> str:
    data = json.dumps(obj, default=str, indent=2).encode("utf-8")
    return store.put_bytes(key, data, "application/json")


def get_json(store: Storage, key: str) -> object:
    return json.loads(store.get_bytes(key).decode("utf-8"))
