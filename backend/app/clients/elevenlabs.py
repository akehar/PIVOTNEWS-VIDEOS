from __future__ import annotations

import httpx


class ElevenLabsClient:
    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def tts_with_timestamps(
        self,
        *,
        voice_id: str,
        text: str,
        model_id: str,
        voice_settings: dict,
        output_format: str,
        timeout: float = 180.0,
    ) -> dict:
        """POST /v1/text-to-speech/{voice_id}/with-timestamps.

        Returns {audio_base64, alignment, normalized_alignment}. `alignment`
        carries per-character start/end times for the original input text.
        """
        url = f"{self.base_url}/v1/text-to-speech/{voice_id}/with-timestamps"
        with httpx.Client(timeout=timeout) as c:
            r = c.post(
                url,
                headers={"xi-api-key": self.api_key, "accept": "application/json"},
                params={"output_format": output_format},
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": voice_settings,
                },
            )
            r.raise_for_status()
            return r.json()
