from __future__ import annotations

import os
import time


class FalClient:
    """FAL: synchronous images, async (submit/poll/collect) video."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def _ensure_key(self) -> None:
        if self.api_key:
            os.environ["FAL_KEY"] = self.api_key

    def run_image(self, model: str, arguments: dict) -> dict:
        import fal_client

        self._ensure_key()
        return fal_client.subscribe(model, arguments=arguments, with_logs=False)

    def submit_video(self, model: str, arguments: dict) -> str:
        """Submit an image-to-video job; return the request id to poll later."""
        import fal_client

        self._ensure_key()
        handle = fal_client.submit(model, arguments=arguments)
        return handle.request_id

    def video_done(self, model: str, request_id: str) -> bool:
        import fal_client

        self._ensure_key()
        status = fal_client.status(model, request_id, with_logs=False)
        return isinstance(status, fal_client.Completed)

    def video_result(self, model: str, request_id: str) -> dict:
        import fal_client

        self._ensure_key()
        return fal_client.result(model, request_id)

    def wait_video(
        self,
        model: str,
        request_id: str,
        *,
        timeout: float = 600.0,
        interval: float = 5.0,
    ) -> dict:
        deadline = time.time() + timeout
        while not self.video_done(model, request_id):
            if time.time() > deadline:
                raise TimeoutError(f"fal video {request_id} timed out")
            time.sleep(interval)
        return self.video_result(model, request_id)
