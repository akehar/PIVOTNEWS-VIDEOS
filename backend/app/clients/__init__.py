from __future__ import annotations

from functools import cached_property

from app.config import Settings, get_settings


class Clients:
    """Lazily-constructed provider clients.

    Each property constructs its client on first use and imports the heavy
    SDK lazily, so importing this module never requires API keys or SDKs.
    Tests inject fakes by assigning the attribute before first access.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @cached_property
    def gemini(self):
        from app.clients.gemini import GeminiClient

        return GeminiClient(self.settings.gemini_api_key)

    @cached_property
    def elevenlabs(self):
        from app.clients.elevenlabs import ElevenLabsClient

        return ElevenLabsClient(
            self.settings.elevenlabs_api_key, self.settings.elevenlabs_api_base
        )

    @cached_property
    def fal(self):
        from app.clients.fal import FalClient

        return FalClient(self.settings.fal_key)

    @cached_property
    def suno(self):
        from app.clients.suno import SunoClient

        return SunoClient(self.settings.suno_api_key, self.settings.suno_api_base)
