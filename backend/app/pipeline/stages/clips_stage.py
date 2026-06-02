from __future__ import annotations

import math

from app.models.beats import Beat
from app.models.job import Job, StageName
from app.pipeline.runner import StageContext, stage
from app.util import download_bytes

# Seedance accepts integer-second durations from 4..15.
_FAL_MIN_DURATION = 4
_FAL_MAX_DURATION = 15


def _requested_duration(job: Job, ctx: StageContext, beat_id: int) -> int:
    ba = job.beat(beat_id)
    target = (
        ba.duration_seconds
        if ba and ba.duration_seconds
        else ctx.config.video.default_clip_seconds
    )
    return max(_FAL_MIN_DURATION, min(_FAL_MAX_DURATION, math.ceil(target)))


def _submit_clip(job: Job, ctx: StageContext, beat: Beat) -> str:
    vs = ctx.config.video
    ba = job.beat(beat.id)
    if ba is None or not ba.image_key:
        raise RuntimeError(f"beat {beat.id} has no image to animate")
    args = {
        "prompt": beat.motion_prompt,
        "image_url": ctx.storage.url(ba.image_key),
        "resolution": vs.resolution,
        "duration": str(_requested_duration(job, ctx, beat.id)),
        "aspect_ratio": vs.aspect_ratio,
        "generate_audio": vs.generate_audio,
    }
    return ctx.clients.fal.submit_video(vs.active_model, args)


def _collect_clip(job: Job, ctx: StageContext, beat: Beat) -> str:
    vs = ctx.config.video
    ba = job.beat(beat.id)
    result = ctx.clients.fal.wait_video(
        vs.active_model,
        ba.clip_request_id,
        timeout=600.0,
        interval=5.0,
    )
    url = result["video"]["url"]
    data = download_bytes(url)
    key = f"jobs/{job.id}/beats/{beat.id}/clip.mp4"
    ctx.storage.put_bytes(key, data, "video/mp4")
    ba.clip_key = key
    ba.clip_request_id = None
    return key


def generate_beat_clip(job: Job, ctx: StageContext, beat: Beat) -> str:
    """Submit + wait for a single beat's clip (used by per-beat regenerate)."""
    ba = job.beat(beat.id)
    ba.clip_request_id = _submit_clip(job, ctx, beat)
    return _collect_clip(job, ctx, beat)


@stage(StageName.clips)
def run_clips(job: Job, ctx: StageContext) -> None:
    if job.script is None:
        raise RuntimeError("no script on job")

    beats = job.script.beats

    # 1) Submit all not-yet-rendered clips (FAL video is async).
    for beat in beats:
        ba = job.beat(beat.id)
        if ba.clip_key and ctx.storage.exists(ba.clip_key):
            continue
        if not ba.clip_request_id:
            ba.clip_request_id = _submit_clip(job, ctx, beat)
            ctx.job_store.save(job)

    # 2) Poll + collect each.
    keys: list[str] = []
    for beat in beats:
        ba = job.beat(beat.id)
        if ba.clip_key and ctx.storage.exists(ba.clip_key):
            keys.append(ba.clip_key)
            continue
        keys.append(_collect_clip(job, ctx, beat))
        ctx.job_store.save(job)

    job.stage(StageName.clips).artifact_keys = keys
