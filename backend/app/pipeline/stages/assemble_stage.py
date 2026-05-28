from __future__ import annotations

import tempfile
from pathlib import Path

from app.models.job import Job, StageName
from app.pipeline.ffmpeg import BeatClip, assemble_video
from app.pipeline.runner import StageContext, stage

# CTA logo lives in the repo, not in artifact storage.
_LOGO_DISK_PATH = Path(__file__).resolve().parents[3] / "assets"


def _fetch(ctx: StageContext, key: str, dest: Path) -> Path:
    dest.write_bytes(ctx.storage.get_bytes(key))
    return dest


@stage(StageName.assemble)
def run_assemble(job: Job, ctx: StageContext) -> None:
    if job.script is None or not job.narration_audio_key:
        raise RuntimeError("script and narration required before assembly")

    ff = ctx.config.ffmpeg
    cta = ctx.config.cta

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        narration = _fetch(ctx, job.narration_audio_key, tmp / "narration.mp3")

        music = None
        if job.music_key:
            music = _fetch(ctx, job.music_key, tmp / "music.mp3")

        beat_clips: list[BeatClip] = []
        for beat in job.script.beats:
            ba = job.beat(beat.id)
            if not ba or not ba.clip_key or not ba.duration_seconds:
                raise RuntimeError(f"beat {beat.id} missing clip or duration")
            clip_path = _fetch(ctx, ba.clip_key, tmp / f"clip_{beat.id}.mp4")
            beat_clips.append(
                BeatClip(path=str(clip_path), duration_seconds=ba.duration_seconds)
            )

        logo = _LOGO_DISK_PATH / Path(cta.logo_path).name
        out = tmp / "final.mp4"
        assemble_video(
            beat_clips=beat_clips,
            narration_path=str(narration),
            music_path=str(music) if music else None,
            out_path=str(out),
            ff=ff,
            cta=cta,
            logo_path=str(logo) if logo.is_file() else None,
        )

        key = f"jobs/{job.id}/final.mp4"
        ctx.storage.put_bytes(key, out.read_bytes(), "video/mp4")

    job.final_video_key = key
    job.stage(StageName.assemble).artifact_keys = [key]
