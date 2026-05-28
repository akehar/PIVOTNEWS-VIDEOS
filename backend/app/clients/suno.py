from __future__ import annotations

import time

import httpx


def _find_audio_url(obj: object) -> str | None:
    """Recursively dig out the first audio URL from a Suno response payload.

    Providers vary (audio_url / audioUrl / stream_audio_url); search defensively.
    """
    keys = ("audio_url", "audioUrl", "source_audio_url", "stream_audio_url")
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for v in obj.values():
            found = _find_audio_url(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_audio_url(v)
            if found:
                return found
    return None


class SunoClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate(
        self, *, brief: str, model: str, instrumental: bool, timeout: float = 60.0
    ) -> str:
        """POST /api/v1/generate -> returns taskId."""
        url = f"{self.base_url}/api/v1/generate"
        with httpx.Client(timeout=timeout) as c:
            r = c.post(
                url,
                headers=self._headers(),
                json={
                    "prompt": brief,
                    "model": model,
                    "instrumental": instrumental,
                    "customMode": False,
                },
            )
            r.raise_for_status()
            data = r.json()
        task_id = data.get("data", {}).get("taskId") or data.get("taskId")
        if not task_id:
            raise RuntimeError(f"suno generate returned no taskId: {data}")
        return task_id

    def fetch(self, task_id: str, timeout: float = 60.0) -> dict:
        url = f"{self.base_url}/api/v1/generate/record-info"
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url, headers=self._headers(), params={"taskId": task_id})
            r.raise_for_status()
            return r.json()

    def wait_audio_url(
        self, task_id: str, *, timeout: float = 300.0, interval: float = 3.0
    ) -> str:
        deadline = time.time() + timeout
        while True:
            payload = self.fetch(task_id)
            url = _find_audio_url(payload)
            if url:
                return url
            if time.time() > deadline:
                raise TimeoutError(f"suno task {task_id} timed out")
            time.sleep(interval)
