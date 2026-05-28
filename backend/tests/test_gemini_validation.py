import json

import pytest

from app.models.pipeline_config import TimingSettings
from app.pipeline.stages.gemini_stage import ScriptValidationError, validate_script


def _script(n_words_per_beat: int, n_beats: int = 3) -> str:
    word = "word"
    beats = [
        {
            "id": i + 1,
            "narration": " ".join([word] * n_words_per_beat),
            "image_prompt": "p",
            "motion_prompt": "m",
            "broll_keywords": ["k"],
        }
        for i in range(n_beats)
    ]
    return json.dumps(
        {
            "desk": "Crypto",
            "writer": "Liam Tanaka",
            "beats": beats,
            "music_brief": "b",
            "cta_text": "c",
        }
    )


def test_valid_script_passes():
    timing = TimingSettings(min_words=185, max_words=290)
    doc = validate_script(_script(70, 3), timing)  # 210 words
    assert doc.total_words == 210
    assert len(doc.beats) == 3


def test_word_count_too_low_rejected():
    timing = TimingSettings(min_words=185, max_words=290)
    with pytest.raises(ScriptValidationError, match="word count"):
        validate_script(_script(10, 3), timing)  # 30 words


def test_bad_json_rejected():
    with pytest.raises(ScriptValidationError, match="not valid JSON"):
        validate_script("not json", TimingSettings())


def test_non_sequential_ids_rejected():
    raw = json.loads(_script(70, 2))
    raw["beats"][1]["id"] = 5
    with pytest.raises(ScriptValidationError, match="sequential"):
        validate_script(json.dumps(raw), TimingSettings(min_words=1, max_words=999))


def test_missing_field_rejected():
    raw = json.loads(_script(70, 2))
    del raw["cta_text"]
    with pytest.raises(ScriptValidationError, match="schema"):
        validate_script(json.dumps(raw), TimingSettings(min_words=1, max_words=999))
