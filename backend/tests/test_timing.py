from app.models.beats import Beat
from app.pipeline.timing import alignment_words, assign_beat_timings, chars_to_words


def _alignment(text: str, dt: float = 0.1) -> dict:
    chars = list(text)
    starts = [round(i * dt, 4) for i in range(len(chars))]
    ends = [round((i + 1) * dt, 4) for i in range(len(chars))]
    return {
        "characters": chars,
        "character_start_times_seconds": starts,
        "character_end_times_seconds": ends,
    }


def test_chars_group_into_words():
    words = chars_to_words(*[
        _alignment("ab cd")[k]
        for k in (
            "characters",
            "character_start_times_seconds",
            "character_end_times_seconds",
        )
    ])
    assert [w.text for w in words] == ["ab", "cd"]
    assert words[0].start == 0.0
    assert words[1].start == 0.3  # char index 3 ('c') * 0.1


def test_assign_beat_timings_tiles_contiguously():
    beats = [
        Beat(id=1, narration="alpha beta", image_prompt="", motion_prompt=""),
        Beat(id=2, narration="gamma", image_prompt="", motion_prompt=""),
    ]
    text = "alpha beta gamma"
    words = alignment_words(_alignment(text))
    audio_dur = len(text) * 0.1  # 1.6s

    timings = assign_beat_timings(beats, words, audio_dur)

    assert timings[0].start_seconds == 0.0
    # beat 2 starts when "gamma" is first spoken (index 11 * 0.1)
    assert timings[1].start_seconds == round(11 * 0.1, 3)
    assert timings[0].end_seconds == timings[1].start_seconds  # no gap
    assert timings[-1].end_seconds == round(audio_dur, 3)  # covers full audio
    covered = sum(t.duration_seconds for t in timings)
    assert abs(covered - audio_dur) < 1e-6


def test_word_count_mismatch_raises():
    beats = [Beat(id=1, narration="one two three", image_prompt="", motion_prompt="")]
    words = alignment_words(_alignment("one two"))  # only 2 words
    try:
        assign_beat_timings(beats, words, 1.0)
        assert False, "expected mismatch error"
    except ValueError as e:
        assert "word" in str(e).lower()
