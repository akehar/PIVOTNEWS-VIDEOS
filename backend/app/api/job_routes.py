from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_config_store, get_job_store
from app.models.job import Job, StageName
from app.pipeline.service import regenerate_beat_media, run_job_by_id
from app.stores.config_store import ConfigStore
from app.stores.job_store import JobStore

router = APIRouter(tags=["jobs"])


class CreateJobRequest(BaseModel):
    desk: str
    topics: str
    writer: str | None = None  # defaults to the desk's configured writer
    autostart: bool = False  # kick off the pipeline immediately


class ArtifactRef(BaseModel):
    label: str
    key: str
    url: str


@router.post("/jobs", response_model=Job, status_code=201)
def create_job(
    req: CreateJobRequest,
    background: BackgroundTasks,
    jobs: JobStore = Depends(get_job_store),
    cfgs: ConfigStore = Depends(get_config_store),
) -> Job:
    cfg = cfgs.get()
    writer = req.writer
    if writer is None:
        match = next((w for w in cfg.writers if w.desk.lower() == req.desk.lower()), None)
        if match is None:
            raise HTTPException(
                400, f"no writer configured for desk '{req.desk}'; pass writer explicitly"
            )
        writer = match.writer

    job = Job(desk=req.desk, writer=writer, topics=req.topics)
    jobs.save(job)
    if req.autostart:
        background.add_task(_run, job.id, None)
    return job


@router.get("/jobs", response_model=list[str])
def list_jobs(jobs: JobStore = Depends(get_job_store)) -> list[str]:
    return jobs.list_ids()


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str, jobs: JobStore = Depends(get_job_store)) -> Job:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


@router.get("/jobs/{job_id}/artifacts", response_model=list[ArtifactRef])
def get_artifacts(
    job_id: str,
    jobs: JobStore = Depends(get_job_store),
) -> list[ArtifactRef]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")

    storage = jobs.storage
    refs: list[ArtifactRef] = []

    def add(label: str, key: str | None) -> None:
        if key:
            refs.append(ArtifactRef(label=label, key=key, url=storage.url(key)))

    add("narration_audio", job.narration_audio_key)
    add("music", job.music_key)
    add("final_video", job.final_video_key)
    for b in job.beats:
        add(f"beat_{b.beat_id}_image", b.image_key)
        add(f"beat_{b.beat_id}_clip", b.clip_key)
    return refs


def _run(job_id: str, until: StageName | None) -> None:
    try:
        run_job_by_id(job_id, until=until)
    except Exception:
        # The runner already persisted the failed stage + error on the job.
        pass


@router.post("/jobs/{job_id}/run", response_model=Job)
def run_job_endpoint(
    job_id: str,
    background: BackgroundTasks,
    until: StageName | None = None,
    jobs: JobStore = Depends(get_job_store),
) -> Job:
    """Kick off (or resume) the pipeline in the background. Poll GET /jobs/{id}."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    background.add_task(_run, job_id, until)
    return job


@router.post("/jobs/{job_id}/beats/{beat_id}/regenerate", response_model=Job)
def regenerate_beat(
    job_id: str,
    beat_id: int,
    jobs: JobStore = Depends(get_job_store),
) -> Job:
    if jobs.get(job_id) is None:
        raise HTTPException(404, "job not found")
    try:
        return regenerate_beat_media(job_id, beat_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
