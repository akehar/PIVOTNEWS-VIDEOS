from __future__ import annotations

from app.models.pipeline_config import PipelineConfig
from app.storage.base import Storage, get_json, put_json

CONFIG_KEY = "config/pipeline_config.json"


class ConfigStore:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def get(self) -> PipelineConfig:
        """Return the stored config, seeding defaults on first access."""
        if not self.storage.exists(CONFIG_KEY):
            cfg = PipelineConfig()
            self.put(cfg)
            return cfg
        return PipelineConfig.model_validate(get_json(self.storage, CONFIG_KEY))

    def put(self, cfg: PipelineConfig) -> PipelineConfig:
        put_json(self.storage, CONFIG_KEY, cfg.model_dump(mode="json"))
        return cfg
