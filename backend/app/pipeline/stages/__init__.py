"""Importing this package registers every pipeline stage with the runner."""
from app.pipeline.stages import (  # noqa: F401
    assemble_stage,
    clips_stage,
    elevenlabs_stage,
    gemini_stage,
    images_stage,
    music_stage,
)
