"""Job model for the resumable staged pipeline.

Stages run in order: gemini -> elevenlabs -> images -> clips -> music ->
assemble. Each stage writes its artifact(s) to R2 and updates status, so a
failed job can be re-run from the first non-complete stage without redoing
prior work.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from app.models.beats import ScriptDoc


class StageName(str, Enum):
    gemini = "gemini"
    elevenlabs = "elevenlabs"
    images = "images"
    clips = "clips"
    music = "music"
    assemble = "assemble"


STAGE_ORDER: list[StageName] = [
    StageName.gemini,
    StageName.elevenlabs,
    StageName.images,
    StageName.clips,
    StageName.music,
    StageName.assemble,
]


class StageState(str, Enum):
    pending = "pending"
    running = "running"
    complete = "complete"
    failed = "failed"


class JobState(str, Enum):
    created = "created"
    running = "running"
    complete = "complete"
    failed = "failed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StageStatus(BaseModel):
    name: StageName
    state: StageState = StageState.pending
    artifact_keys: list[str] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BeatArtifact(BaseModel):
    """Per-beat measured timing and rendered media, keyed by beat id."""

    beat_id: int
    # Measured from the narration audio (the master clock):
    start_seconds: float | None = None
    end_seconds: float | None = None
    duration_seconds: float | None = None
    # R2 keys for this beat's rendered media:
    image_key: str | None = None
    clip_key: str | None = None
    # FAL async request id for the in-flight Seedance clip:
    clip_request_id: str | None = None


class Job(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    desk: str
    writer: str
    topics: str
    state: JobState = JobState.created
    stages: list[StageStatus] = Field(
        default_factory=lambda: [StageStatus(name=n) for n in STAGE_ORDER]
    )

    # Artifacts produced along the way (R2 keys unless noted):
    script: ScriptDoc | None = None
    narration_audio_key: str | None = None
    audio_duration_seconds: float | None = None
    beats: list[BeatArtifact] = Field(default_factory=list)
    music_key: str | None = None
    final_video_key: str | None = None

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def stage(self, name: StageName) -> StageStatus:
        for s in self.stages:
            if s.name == name:
                return s
        raise KeyError(name)

    def next_stage(self) -> StageName | None:
        """First stage that is not yet complete (resume point)."""
        for s in self.stages:
            if s.state != StageState.complete:
                return s.name
        return None

    def beat(self, beat_id: int) -> BeatArtifact | None:
        for b in self.beats:
            if b.beat_id == beat_id:
                return b
        return None

    def touch(self) -> None:
        self.updated_at = _now()
