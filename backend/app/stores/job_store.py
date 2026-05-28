from __future__ import annotations

from app.models.job import Job
from app.storage.base import Storage, get_json, put_json

JOBS_PREFIX = "jobs/"


def job_key(job_id: str) -> str:
    return f"{JOBS_PREFIX}{job_id}/job.json"


class JobStore:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def save(self, job: Job) -> Job:
        job.touch()
        put_json(self.storage, job_key(job.id), job.model_dump(mode="json"))
        return job

    def get(self, job_id: str) -> Job | None:
        key = job_key(job_id)
        if not self.storage.exists(key):
            return None
        return Job.model_validate(get_json(self.storage, key))

    def list_ids(self) -> list[str]:
        ids: list[str] = []
        for key in self.storage.list_prefix(JOBS_PREFIX):
            if key.endswith("/job.json"):
                ids.append(key[len(JOBS_PREFIX) : -len("/job.json")])
        return ids
