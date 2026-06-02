from __future__ import annotations

from app.models.job import Job, StageName
from app.pipeline.runner import StageContext, stage
from app.util import download_bytes


@stage(StageName.music)
def run_music(job: Job, ctx: StageContext) -> None:
    if job.script is None:
        raise RuntimeError("no script on job")

    ms = ctx.config.music
    brief = job.script.music_brief.strip() or ms.default_brief

    task_id = ctx.clients.suno.generate(
        brief=brief, model=ms.model, instrumental=ms.instrumental
    )
    url = ctx.clients.suno.wait_audio_url(
        task_id,
        timeout=ms.poll_timeout_seconds,
        interval=ms.poll_interval_seconds,
    )
    data = download_bytes(url)
    key = f"jobs/{job.id}/music.mp3"
    ctx.storage.put_bytes(key, data, "audio/mpeg")

    job.music_key = key
    job.stage(StageName.music).artifact_keys = [key]
