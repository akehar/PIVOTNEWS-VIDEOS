from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_config_store
from app.models.pipeline_config import PipelineConfig
from app.stores.config_store import ConfigStore

router = APIRouter(tags=["config"])


@router.get("/config", response_model=PipelineConfig)
def read_config(store: ConfigStore = Depends(get_config_store)) -> PipelineConfig:
    return store.get()


@router.put("/config", response_model=PipelineConfig)
def write_config(
    cfg: PipelineConfig, store: ConfigStore = Depends(get_config_store)
) -> PipelineConfig:
    return store.put(cfg)
