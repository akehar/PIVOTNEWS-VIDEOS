"""The Gemini data contract: a script is a list of BEATS.

Narration is the master clock. Each beat owns one narration line, one
image prompt, one motion prompt and b-roll keywords. One beat = one image
= one clip.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


class Beat(BaseModel):
    id: int
    narration: str
    image_prompt: str
    motion_prompt: str
    broll_keywords: list[str] = Field(default_factory=list)

    @property
    def word_count(self) -> int:
        return count_words(self.narration)


class ScriptDoc(BaseModel):
    """Exactly the schema Gemini must return (validated before proceeding)."""

    desk: str
    writer: str
    beats: list[Beat]
    music_brief: str
    cta_text: str

    @property
    def total_words(self) -> int:
        return sum(b.word_count for b in self.beats)

    @property
    def narration_text(self) -> str:
        """Full narration rendered to ElevenLabs as one take."""
        return " ".join(b.narration.strip() for b in self.beats)
