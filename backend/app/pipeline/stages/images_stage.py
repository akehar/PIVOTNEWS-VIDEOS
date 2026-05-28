from __future__ import annotations

from app.models.beats import Beat
from app.models.job import Job, StageName
from app.pipeline.runner import StageContext, stage
from app.util import download_bytes


def generate_beat_image(job: Job, ctx: StageContext, beat: Beat) -> str:
    """Render one beat's still via FAL and store it. Returns the storage key."""
    im = ctx.config.images
    result = ctx.clients.fal.run_image(
        im.model,
        {
            "prompt": beat.image_prompt,
            "aspect_ratio": im.aspect_ratio,
            "num_images": 1,
            "output_format": im.output_format,
            "resolution": im.resolution,
            "safety_tolerance": im.safety_tolerance,
        },
    )
    url = result["images"][0]["url"]
    data = download_bytes(url)
    key = f"jobs/{job.id}/beats/{beat.id}/image.{im.output_format}"
    ctx.storage.put_bytes(key, data, f"image/{im.output_format}")

    ba = job.beat(beat.id)
    if ba is not None:
        ba.image_key = key
    return key


@stage(StageName.images)
def run_images(job: Job, ctx: StageContext) -> None:
    if job.script is None:
        raise RuntimeError("no script on job")

    keys: list[str] = []
    for beat in job.script.beats:
        ba = job.beat(beat.id)
        # Resumable per-beat: skip beats already rendered.
        if ba and ba.image_key and ctx.storage.exists(ba.image_key):
            keys.append(ba.image_key)
            continue
        keys.append(generate_beat_image(job, ctx, beat))
        ctx.job_store.save(job)

    job.stage(StageName.images).artifact_keys = keys
