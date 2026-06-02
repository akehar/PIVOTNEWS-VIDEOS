"""End-to-end pipeline run: all six stages, fake providers, REAL ffmpeg.

Network providers (Gemini/ElevenLabs/FAL/Suno) are faked, but every fake
serves real bytes over a local HTTP server so the actual download/decode/
ffprobe/ffmpeg code paths execute. The assembled mp4 is probed to confirm
timing and dimensions.
"""
from __future__ import annotations

import base64
import json
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.clients import Clients
from app.models.job import Job, JobState
from app.models.pipeline_config import PipelineConfig
from app.pipeline import stages  # noqa: F401  registers stages
from app.pipeline.ffmpeg import ffprobe_duration, ffprobe_resolution
from app.pipeline.runner import StageContext, run_job
from app.storage.local import LocalStorage
from app.stores.config_store import ConfigStore
from app.stores.job_store import JobStore

DT = 0.06  # seconds per character in the fake alignment

BEATS = [
    ("Bitcoin spot ETFs just posted their largest single day inflow on record.",
     "macro chart", "slow push in on a glowing chart"),
    ("Regulators meanwhile signalled fresh scrutiny of staking rewards programs.",
     "regulator building", "subtle pan across a marble facade"),
    ("Traders are now weighing whether the rally has real staying power.",
     "trading desk", "gentle dolly past a wall of screens"),
]


def _gen_media(path: Path, kind: str, duration: float) -> None:
    if kind == "png":
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
               "color=c=navy:s=720x1280", "-frames:v", "1", str(path)]
    elif kind == "mp4":
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
               f"testsrc=size=720x1280:rate=30:duration={duration}",
               "-pix_fmt", "yuv420p", str(path)]
    elif kind == "narration":
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
               f"anullsrc=r=44100:cl=mono", "-t", f"{duration}", str(path)]
    elif kind == "music":
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
               f"sine=frequency=330:duration={duration}", str(path)]
    else:
        raise ValueError(kind)
    subprocess.run(cmd, capture_output=True, check=True)


class MediaServer:
    def __init__(self, root: Path):
        self.root = root
        handler = partial(SimpleHTTPRequestHandler, directory=str(root))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def url(self, name: str) -> str:
        return f"http://127.0.0.1:{self.port}/{name}"

    def stop(self) -> None:
        self.httpd.shutdown()


class FakeGemini:
    def generate_json(self, model, system_prompt, user_prompt, temperature) -> str:
        return json.dumps({
            "desk": "Crypto",
            "writer": "Liam Tanaka",
            "beats": [
                {"id": i + 1, "narration": n, "image_prompt": ip,
                 "motion_prompt": mp, "broll_keywords": ["crypto"]}
                for i, (n, ip, mp) in enumerate(BEATS)
            ],
            "music_brief": "low-key news underscore",
            "cta_text": "Follow pivotnews.ai",
        })


class FakeElevenLabs:
    def __init__(self, server: MediaServer):
        self.server = server

    def tts_with_timestamps(self, *, voice_id, text, model_id,
                            voice_settings, output_format):
        chars = list(text)
        starts = [round(i * DT, 4) for i in range(len(chars))]
        ends = [round((i + 1) * DT, 4) for i in range(len(chars))]
        dur = round(len(chars) * DT, 2)
        path = self.server.root / "narration.mp3"
        _gen_media(path, "narration", dur)
        return {
            "audio_base64": base64.b64encode(path.read_bytes()).decode(),
            "alignment": {
                "characters": chars,
                "character_start_times_seconds": starts,
                "character_end_times_seconds": ends,
            },
        }


class FakeFal:
    def __init__(self, server: MediaServer):
        self.server = server
        self._submitted: dict[str, float] = {}
        self._n = 0

    def run_image(self, model, arguments):
        self._n += 1
        name = f"img_{self._n}.png"
        _gen_media(self.server.root / name, "png", 0)
        return {"images": [{"url": self.server.url(name), "content_type": "image/png"}]}

    def submit_video(self, model, arguments):
        self._n += 1
        rid = f"req_{self._n}"
        self._submitted[rid] = float(arguments["duration"])
        return rid

    def wait_video(self, model, request_id, *, timeout, interval):
        name = f"clip_{request_id}.mp4"
        _gen_media(self.server.root / name, "mp4", self._submitted[request_id])
        return {"video": {"url": self.server.url(name)}}


class FakeSuno:
    def __init__(self, server: MediaServer):
        self.server = server

    def generate(self, *, brief, model, instrumental):
        return "task_1"

    def wait_audio_url(self, task_id, *, timeout, interval):
        _gen_media(self.server.root / "music.mp3", "music", 8.0)
        return self.server.url("music.mp3")


@pytest.fixture
def server(tmp_path):
    s = MediaServer(tmp_path / "served")
    (tmp_path / "served").mkdir()
    yield s
    s.stop()


def test_full_pipeline_produces_video(tmp_path, server):
    storage = LocalStorage(str(tmp_path / "store"))

    cfg = PipelineConfig()
    cfg.writers[0].voice_id = "voice_liam"
    cfg.timing.min_words = 1  # exercise mechanics, not the word budget
    cfg.timing.max_words = 10_000
    ConfigStore(storage).put(cfg)

    clients = Clients()
    clients.gemini = FakeGemini()
    clients.elevenlabs = FakeElevenLabs(server)
    clients.fal = FakeFal(server)
    clients.suno = FakeSuno(server)

    job_store = JobStore(storage)
    ctx = StageContext(config=cfg, storage=storage, job_store=job_store, clients=clients)

    job = Job(desk="Crypto", writer="Liam Tanaka", topics="ETF inflows; staking rules")
    job_store.save(job)

    run_job(job, ctx)

    assert job.state == JobState.complete
    assert job.next_stage() is None
    assert job.script is not None and len(job.script.beats) == 3
    assert job.audio_duration_seconds and job.audio_duration_seconds > 0

    # every beat got timing + media
    for ba in job.beats:
        assert ba.duration_seconds and ba.duration_seconds > 0
        assert ba.image_key and storage.exists(ba.image_key)
        assert ba.clip_key and storage.exists(ba.clip_key)

    assert job.final_video_key and storage.exists(job.final_video_key)

    # probe the assembled video
    out = tmp_path / "final.mp4"
    out.write_bytes(storage.get_bytes(job.final_video_key))
    w, h = ffprobe_resolution(str(out))
    assert (w, h) == (1080, 1920)

    expected = sum(ba.duration_seconds for ba in job.beats) + cfg.cta.duration_seconds
    assert abs(ffprobe_duration(str(out)) - expected) < 0.7
