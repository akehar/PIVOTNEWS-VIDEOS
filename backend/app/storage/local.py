from __future__ import annotations

from pathlib import Path


class LocalStorage:
    """Filesystem-backed store used when R2 is not configured (local dev).

    Mirrors the R2 key layout under a base directory so the rest of the
    pipeline is storage-agnostic.
    """

    def __init__(self, base_dir: str) -> None:
        self.base = Path(base_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.base / key).resolve()
        if not str(p).startswith(str(self.base)):
            raise ValueError(f"key escapes storage root: {key}")
        return p

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def url(self, key: str) -> str:
        return self._path(key).as_uri()

    def list_prefix(self, prefix: str) -> list[str]:
        root = self._path(prefix) if prefix else self.base
        search_root = root if root.is_dir() else self.base
        out: list[str] = []
        for p in search_root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self.base).as_posix()
                if rel.startswith(prefix):
                    out.append(rel)
        return out
