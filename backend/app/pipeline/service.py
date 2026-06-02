"""Pipeline orchestration entrypoints used by the API layer."""
from __future__ import annotations

from app.clients import Clients
from app.models.job import Job, StageName, StageState
from app.pipeline import stages  # noqa: F401  (registers all stages)
from app.pipeline.runner import StageContext, run_job
from app.pipeline.stages.clips_stage import generate_beat_clip
from app.pipeline.stages.images_stage import generate_beat_image
from app.storage.factory import get_storage
from app.stores.config_store import ConfigStore
from app.stores.job_store import JobStore


def build_context() -> StageContext:
    storage = get_storage()
    return StageContext(
        config=ConfigStore(storage).get(),
        storage=storage,
        job_store=JobStore(storage),
        clients=Clients(),
    )


def run_job_by_id(job_id: str, until: StageName | None = None) -> Job:
    ctx = build_context()
    job = ctx.job_store.get(job_id)
    if job is None:
        raise KeyError(job_id)
    return run_job(job, ctx, until=until)


def regenerate_beat_media(job_id: str, beat_id: int) -> Job:
    """Re-render one beat's image + clip and invalidate the final assembly."""
    ctx = build_context()
    job = ctx.job_store.get(job_id)
    if job is None:
        raise KeyError(job_id)
    if job.script is None:
        raise ValueError("job has no script yet")
    beat = next((b for b in job.script.beats if b.id == beat_id), None)
    if beat is None:
        raise ValueError(f"beat {beat_id} not found")

    generate_beat_image(job, ctx, beat)
    generate_beat_clip(job, ctx, beat)

    # The final video no longer reflects this beat; require re-assembly.
    assemble = job.stage(StageName.assemble)
    assemble.state = StageState.pending
    assemble.artifact_keys = []
    job.final_video_key = None

    ctx.job_store.save(job)
    return job
