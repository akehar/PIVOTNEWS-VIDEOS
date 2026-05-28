from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from app.models.job import Job, StageName
from app.pipeline.ffmpeg import ffprobe_duration
from app.pipeline.runner import StageContext, stage
from app.pipeline.timing import alignment_words, assign_beat_timings

# Tolerance between the last aligned word and the measured audio length.
_AUDIO_MATCH_TOLERANCE_S = 1.0


@stage(StageName.elevenlabs)
def run_elevenlabs(job: Job, ctx: StageContext) -> None:
    if job.script is None:
        raise RuntimeError("no script on job; run gemini stage first")

    cfg = ctx.config
    el = cfg.elevenlabs
    wv = cfg.voice_for(job.writer)
    if wv is None or not wv.voice_id:
        raise RuntimeError(
            f"no ElevenLabs voice_id configured for writer '{job.writer}'"
        )

    resp = ctx.clients.elevenlabs.tts_with_timestamps(
        voice_id=wv.voice_id,
        text=job.script.narration_text,
        model_id=el.model_id,
        voice_settings={
            "stability": el.stability,
            "similarity_boost": el.similarity_boost,
            "style": el.style,
            "use_speaker_boost": el.use_speaker_boost,
        },
        output_format=el.output_format,
    )

    audio = base64.b64decode(resp["audio_base64"])
    audio_key = f"jobs/{job.id}/narration.mp3"
    ctx.storage.put_bytes(audio_key, audio, "audio/mpeg")

    # Measure true audio length from the rendered file.
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "narration.mp3"
        p.write_bytes(audio)
        audio_duration = ffprobe_duration(str(p))

    words = alignment_words(resp["alignment"])
    if not words:
        raise RuntimeError("ElevenLabs returned no word timings")

    timings = assign_beat_timings(job.script.beats, words, audio_duration)

    # Assert the timing math against the audio length (spec requirement).
    last_word_end = words[-1].end
    if abs(audio_duration - last_word_end) > _AUDIO_MATCH_TOLERANCE_S:
        raise RuntimeError(
            f"timing mismatch: audio length {audio_duration:.2f}s vs last word "
            f"end {last_word_end:.2f}s (>{_AUDIO_MATCH_TOLERANCE_S}s apart)"
        )
    covered = sum(t.duration_seconds for t in timings)
    if abs(covered - audio_duration) > 1e-2:
        raise RuntimeError(
            f"beat segments cover {covered:.2f}s but audio is {audio_duration:.2f}s"
        )

    for t in timings:
        ba = job.beat(t.beat_id)
        if ba is None:
            raise RuntimeError(f"no beat artifact for beat {t.beat_id}")
        ba.start_seconds = t.start_seconds
        ba.end_seconds = t.end_seconds
        ba.duration_seconds = t.duration_seconds

    job.narration_audio_key = audio_key
    job.audio_duration_seconds = round(audio_duration, 3)
    job.stage(StageName.elevenlabs).artifact_keys = [audio_key]
