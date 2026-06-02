"""Timing math: narration is the master clock.

ElevenLabs returns CHARACTER-level timestamps. We group characters into
spoken words, map words onto beats (one beat owns a contiguous run of
words), then expand each beat to a contiguous on-screen SEGMENT that
includes the pause after it. The segments tile [0, audio_duration] with no
gaps, so the concatenated clips line up exactly with the narration.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.beats import Beat


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class BeatTiming:
    beat_id: int
    start_seconds: float  # segment start (on-screen)
    end_seconds: float  # segment end (= next beat's spoken start, or audio end)
    duration_seconds: float
    spoken_start: float  # first word of the beat
    spoken_end: float  # last word of the beat


def chars_to_words(
    characters: list[str],
    starts: list[float],
    ends: list[float],
) -> list[Word]:
    if not (len(characters) == len(starts) == len(ends)):
        raise ValueError("alignment arrays have mismatched lengths")
    words: list[Word] = []
    buf: list[str] = []
    w_start = 0.0
    w_end = 0.0
    for ch, s, e in zip(characters, starts, ends):
        if ch.isspace():
            if buf:
                words.append(Word("".join(buf), w_start, w_end))
                buf = []
            continue
        if not buf:
            w_start = s
        buf.append(ch)
        w_end = e
    if buf:
        words.append(Word("".join(buf), w_start, w_end))
    return words


def alignment_words(alignment: dict) -> list[Word]:
    return chars_to_words(
        alignment["characters"],
        alignment["character_start_times_seconds"],
        alignment["character_end_times_seconds"],
    )


def _token_count(narration: str) -> int:
    return len(narration.split())


def assign_beat_timings(
    beats: list[Beat],
    words: list[Word],
    audio_duration: float,
) -> list[BeatTiming]:
    """Map aligned words onto beats and tile contiguous on-screen segments.

    Raises if the spoken word count doesn't match the beats' token count
    (the spec's "assert math" guard) or if audio_duration is too short.
    """
    if not beats:
        raise ValueError("no beats to time")

    spoken: list[tuple[int, float, float]] = []  # (beat_id, first_start, last_end)
    idx = 0
    for b in beats:
        n = _token_count(b.narration)
        if n == 0:
            raise ValueError(f"beat {b.id} has empty narration")
        chunk = words[idx : idx + n]
        if len(chunk) < n:
            raise ValueError(
                f"beat {b.id} expected {n} words but only "
                f"{len(chunk)} aligned words remain"
            )
        spoken.append((b.id, chunk[0].start, chunk[-1].end))
        idx += n

    if idx != len(words):
        raise ValueError(
            f"word-count mismatch: beats tokenize to {idx} words but "
            f"alignment produced {len(words)}"
        )

    last_spoken_end = spoken[-1][2]
    if audio_duration + 1e-3 < last_spoken_end:
        raise ValueError(
            f"audio_duration {audio_duration:.3f}s shorter than last spoken "
            f"word end {last_spoken_end:.3f}s"
        )

    timings: list[BeatTiming] = []
    for i, (bid, sp_start, sp_end) in enumerate(spoken):
        seg_start = 0.0 if i == 0 else spoken[i][1]
        seg_end = spoken[i + 1][1] if i + 1 < len(spoken) else audio_duration
        if seg_end <= seg_start:
            raise ValueError(
                f"beat {bid} non-positive segment ({seg_start:.3f}..{seg_end:.3f})"
            )
        timings.append(
            BeatTiming(
                beat_id=bid,
                start_seconds=round(seg_start, 3),
                end_seconds=round(seg_end, 3),
                duration_seconds=round(seg_end - seg_start, 3),
                spoken_start=round(sp_start, 3),
                spoken_end=round(sp_end, 3),
            )
        )
    return timings
