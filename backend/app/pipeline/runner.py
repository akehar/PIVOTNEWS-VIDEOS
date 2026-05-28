"""Resumable staged pipeline runner.

Stages run in STAGE_ORDER. Each registered stage function takes (job, ctx),
does its work, writes artifacts to storage, mutates the job, and returns.
The runner marks stage state and persists the job after every stage, so a
failed job resumes from its first non-complete stage.

Phase 1 ships the framework only: the stage implementations land in Phases
2-6 and register themselves via @stage(...). Unregistered stages raise so a
run stops cleanly at the first unimplemented step.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models.job import Job, JobState, StageName, StageState, _now
from app.models.pipeline_config import PipelineConfig
from app.storage.base import Storage
from app.stores.job_store import JobStore


@dataclass
class StageContext:
    config: PipelineConfig
    storage: Storage
    job_store: JobStore


StageFn = Callable[[Job, StageContext], None]

_REGISTRY: dict[StageName, StageFn] = {}


def stage(name: StageName) -> Callable[[StageFn], StageFn]:
    def deco(fn: StageFn) -> StageFn:
        _REGISTRY[name] = fn
        return fn

    return deco


def run_job(job: Job, ctx: StageContext, *, until: StageName | None = None) -> Job:
    """Run from the first non-complete stage to the end (or `until`, inclusive)."""
    job.state = JobState.running
    ctx.job_store.save(job)

    for st in job.stages:
        if st.state == StageState.complete:
            continue

        fn = _REGISTRY.get(st.name)
        if fn is None:
            st.state = StageState.failed
            st.error = f"stage '{st.name.value}' not implemented yet"
            ctx.job_store.save(job)
            raise NotImplementedError(st.error)

        st.state = StageState.running
        st.started_at = _now()
        st.error = None
        ctx.job_store.save(job)

        try:
            fn(job, ctx)
        except Exception as e:  # stage failed; persist and stop (resumable)
            st.state = StageState.failed
            st.error = str(e)
            st.finished_at = _now()
            job.state = JobState.failed
            ctx.job_store.save(job)
            raise

        st.state = StageState.complete
        st.finished_at = _now()
        ctx.job_store.save(job)

        if until is not None and st.name == until:
            break

    job.state = (
        JobState.complete if job.next_stage() is None else JobState.running
    )
    ctx.job_store.save(job)
    return job
