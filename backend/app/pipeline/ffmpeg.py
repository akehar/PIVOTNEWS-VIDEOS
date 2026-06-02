"""FFmpeg assembly. Runs on Render (system ffmpeg), not on FAL.

Each beat clip is scaled/cropped to the target frame, then trimmed/padded
to its measured segment duration so the visuals track the narration. A
branded CTA card is generated with drawtext and appended. Music is looped,
ducked under the narration, cross-faded, and mixed with the (silence-padded)
narration track.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.models.pipeline_config import CTASettings, FFmpegSettings

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]


@dataclass
class BeatClip:
    path: str
    duration_seconds: float


def _font_file() -> str | None:
    for f in _FONT_CANDIDATES:
        if Path(f).is_file():
            return f
    return None


def ffprobe_duration(path: str) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def ffprobe_resolution(path: str) -> tuple[int, int]:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", path,
        ],
        capture_output=True, text=True, check=True,
    )
    s = json.loads(out.stdout)["streams"][0]
    return int(s["width"]), int(s["height"])


def _escape_drawtext(text: str) -> str:
    # drawtext is sensitive to : ' \ and %
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def build_assembly_command(
    *,
    beat_clips: list[BeatClip],
    narration_path: str,
    music_path: str | None,
    out_path: str,
    ff: FFmpegSettings,
    cta: CTASettings,
    logo_path: str | None,
) -> list[str]:
    if not beat_clips:
        raise ValueError("no beat clips to assemble")

    w, h = (int(x) for x in ff.resolution.lower().split("x"))
    fps = ff.fps
    cf = max(ff.crossfade_ms, 0) / 1000.0
    cta_dur = cta.duration_seconds
    narration_total = sum(c.duration_seconds for c in beat_clips)
    total = narration_total + cta_dur

    cmd: list[str] = ["ffmpeg", "-y"]
    for c in beat_clips:
        cmd += ["-i", c.path]
    n = len(beat_clips)
    narr_idx = n
    cmd += ["-i", narration_path]
    music_idx = None
    if music_path:
        music_idx = n + 1
        cmd += ["-i", music_path]
    # CTA background as a lavfi color source.
    cmd += [
        "-f", "lavfi", "-t", f"{cta_dur}",
        "-i", f"color=c={cta.brand_color}:s={w}x{h}:r={fps}",
    ]
    cta_idx = (music_idx if music_idx is not None else narr_idx) + 1
    logo_idx = None
    if logo_path and Path(logo_path).is_file():
        logo_idx = cta_idx + 1
        cmd += ["-i", logo_path]

    parts: list[str] = []

    # --- per-beat video segments ---
    vlabels = []
    for i, c in enumerate(beat_clips):
        lbl = f"v{i}"
        parts.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},fps={fps},setpts=PTS-STARTPTS,"
            f"tpad=stop_mode=clone:stop_duration={c.duration_seconds},"
            f"trim=duration={c.duration_seconds},setpts=PTS-STARTPTS[{lbl}]"
        )
        vlabels.append(f"[{lbl}]")

    # --- CTA card (drawtext + optional logo) ---
    font = _font_file()
    fontspec = f"fontfile={font}:" if font else ""
    drawtext = (
        f"drawtext={fontspec}text='{_escape_drawtext(cta.text)}':"
        f"fontcolor={cta.font_color}:fontsize={cta.font_size}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2"
    )
    if logo_idx is not None:
        parts.append(
            f"[{cta_idx}:v]{drawtext}[ctabg];"
            f"[{logo_idx}:v]scale={w // 3}:-1[logo];"
            f"[ctabg][logo]overlay=(W-w)/2:H*0.25,fps={fps},"
            f"setpts=PTS-STARTPTS[cta]"
        )
    else:
        parts.append(
            f"[{cta_idx}:v]{drawtext},fps={fps},setpts=PTS-STARTPTS[cta]"
        )
    vlabels.append("[cta]")

    # --- concat all video segments ---
    parts.append("".join(vlabels) + f"concat=n={n + 1}:v=1:a=0[vout]")

    # --- audio: narration padded with CTA silence, music ducked + mixed ---
    parts.append(
        f"[{narr_idx}:a]apad,atrim=0:{total},asetpts=PTS-STARTPTS[narr]"
    )
    if music_idx is not None:
        fade_out_start = max(total - cf, 0.0)
        parts.append(
            f"[{music_idx}:a]aloop=loop=-1:size=2000000000,"
            f"atrim=0:{total},asetpts=PTS-STARTPTS,"
            f"volume={ff.music_duck_db}dB,"
            f"afade=t=in:st=0:d={cf},"
            f"afade=t=out:st={fade_out_start}:d={cf}[mus]"
        )
        parts.append(
            "[narr][mus]amix=inputs=2:duration=first:normalize=0[aout]"
        )
    else:
        parts.append("[narr]anull[aout]")

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[vout]", "-map", "[aout]",
        "-r", str(fps),
        "-c:v", ff.video_codec, "-pix_fmt", ff.pixel_format,
        "-c:a", ff.audio_codec, "-b:a", ff.audio_bitrate,
        "-t", f"{total}",
        out_path,
    ]
    return cmd


def assemble_video(
    *,
    beat_clips: list[BeatClip],
    narration_path: str,
    music_path: str | None,
    out_path: str,
    ff: FFmpegSettings,
    cta: CTASettings,
    logo_path: str | None = None,
) -> str:
    cmd = build_assembly_command(
        beat_clips=beat_clips,
        narration_path=narration_path,
        music_path=music_path,
        out_path=out_path,
        ff=ff,
        cta=cta,
        logo_path=logo_path,
    )
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr[-4000:]}")
    return out_path
