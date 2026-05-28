"""The ONE editable JSON config doc. Every tweakable parameter lives here.

Exposed via GET/PUT /config. Defaults below are the seed document; they
can be edited at runtime without a redeploy. Nothing in the pipeline is
hardcoded — stages read their parameters from this doc.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_GEMINI_SYSTEM_PROMPT = """\
You are the script engine for pivotnews.ai short-form vertical videos.
You turn a news desk's daily topics into a tightly-timed narration broken
into BEATS, written in the voice of the named desk writer.

TIMING IS THE MASTER CLOCK. Narration drives everything downstream.
Reference: ~34 spoken words plus ~2.4s of natural pauses is about 11s of
narration (~185 words-per-minute including pauses). The finished video must
land between 60 and 90 seconds, so the TOTAL spoken words across all beats
MUST be between {min_words} and {max_words}.

Return STRICT JSON ONLY, matching exactly this schema (no markdown, no prose):
{{
  "desk": str,
  "writer": str,
  "beats": [
    {{
      "id": int,                     // 1-based, sequential
      "narration": str,              // one or two spoken sentences
      "image_prompt": str,           // a vivid still-image prompt for this beat
      "motion_prompt": str,          // how that still should move (image-to-video)
      "broll_keywords": [str]        // 3-6 short keywords
    }}
  ],
  "music_brief": str,                // a short brief for the music bed
  "cta_text": str                    // closing call-to-action line
}}

Rules:
- Write narration in {writer}'s voice for the {desk} desk.
- Each beat is one visual moment. Keep beats between 5 and 9 of them.
- image_prompt must be self-contained (no references to other beats).
- motion_prompt describes a subtle 3-5s camera/subject move, no cuts.
- Do not include any text outside the JSON object.
"""


class WriterVoice(BaseModel):
    writer: str
    desk: str
    voice_id: str  # ElevenLabs voice id for this writer


class ElevenLabsSettings(BaseModel):
    # eleven_v3 alignment model returns char/word timing; v2 multilingual also
    # supports the with-timestamps endpoint. Swappable here.
    model_id: str = "eleven_multilingual_v2"
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True
    # mp3_44100_128 keeps the with-timestamps endpoint happy and is small.
    output_format: str = "mp3_44100_128"


class GeminiSettings(BaseModel):
    model: str = "gemini-2.5-pro"
    temperature: float = 0.7
    system_prompt: str = DEFAULT_GEMINI_SYSTEM_PROMPT
    max_retries: int = 3


class TimingSettings(BaseModel):
    target_wpm: int = 185
    min_words: int = 185
    max_words: int = 290
    target_min_seconds: float = 60.0
    target_max_seconds: float = 90.0


class ImageSettings(BaseModel):
    model: str = "fal-ai/nano-banana-2"
    aspect_ratio: str = "9:16"
    resolution: str = "1K"
    output_format: str = "png"
    num_images: int = 1
    safety_tolerance: int = 4


class VideoSettings(BaseModel):
    # Default Seedance 2.0 image-to-video. VIDEO_MODEL swaps to a cheaper/faster
    # slug during testing (see model + use_fast).
    model: str = "bytedance/seedance-2.0/image-to-video"
    fast_model: str = "bytedance/seedance-2.0/fast/image-to-video"
    use_fast: bool = False  # VIDEO_MODEL test flag: route to fast_model
    resolution: str = "720p"
    aspect_ratio: str = "9:16"
    default_clip_seconds: float = 4.0
    min_clip_seconds: float = 3.0
    max_clip_seconds: float = 5.0
    generate_audio: bool = False  # silent clips; narration is the audio

    @property
    def active_model(self) -> str:
        return self.fast_model if self.use_fast else self.model


class MusicSettings(BaseModel):
    model: str = "V4_5"
    instrumental: bool = True
    default_brief: str = "Subtle modern news-bed underscore, low-key, no vocals."
    poll_interval_seconds: float = 3.0
    poll_timeout_seconds: float = 300.0


class FFmpegSettings(BaseModel):
    resolution: str = "1080x1920"  # 9:16
    fps: int = 30
    music_duck_db: float = -20.0  # duck music under narration
    crossfade_ms: int = 500
    audio_bitrate: str = "192k"
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    pixel_format: str = "yuv420p"


class CTASettings(BaseModel):
    brand_color: str = "#E8593C"
    logo_path: str = "assets/logo.png"
    text: str = "pivotnews.ai"
    duration_seconds: float = 3.0
    font_size: int = 84
    font_color: str = "#FFFFFF"


class PipelineConfig(BaseModel):
    aspect_ratio: str = "9:16"
    writers: list[WriterVoice] = Field(
        default_factory=lambda: [
            WriterVoice(writer="Liam Tanaka", desk="Crypto", voice_id="")
        ]
    )
    elevenlabs: ElevenLabsSettings = Field(default_factory=ElevenLabsSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    timing: TimingSettings = Field(default_factory=TimingSettings)
    images: ImageSettings = Field(default_factory=ImageSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    music: MusicSettings = Field(default_factory=MusicSettings)
    ffmpeg: FFmpegSettings = Field(default_factory=FFmpegSettings)
    cta: CTASettings = Field(default_factory=CTASettings)

    def voice_for(self, writer: str) -> WriterVoice | None:
        for w in self.writers:
            if w.writer.lower() == writer.lower():
                return w
        return None
