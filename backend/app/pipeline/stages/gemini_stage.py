from __future__ import annotations

import json

from pydantic import ValidationError

from app.models.beats import ScriptDoc
from app.models.job import BeatArtifact, Job, StageName
from app.models.pipeline_config import TimingSettings
from app.pipeline.runner import StageContext, stage
from app.storage.base import put_json


class ScriptValidationError(Exception):
    pass


def validate_script(raw_text: str, timing: TimingSettings) -> ScriptDoc:
    """Parse + validate Gemini output against the beats contract.

    Raises ScriptValidationError on bad JSON, schema mismatch, non-sequential
    beat ids, or a total word count outside the configured band.
    """
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as e:
        raise ScriptValidationError(f"output is not valid JSON: {e}") from e

    try:
        doc = ScriptDoc.model_validate(data)
    except ValidationError as e:
        raise ScriptValidationError(f"schema mismatch: {e}") from e

    if not doc.beats:
        raise ScriptValidationError("beats list is empty")

    expected_ids = list(range(1, len(doc.beats) + 1))
    if [b.id for b in doc.beats] != expected_ids:
        raise ScriptValidationError(
            f"beat ids must be sequential 1..N, got {[b.id for b in doc.beats]}"
        )

    wc = doc.total_words
    if not (timing.min_words <= wc <= timing.max_words):
        raise ScriptValidationError(
            f"total word count {wc} outside [{timing.min_words}, {timing.max_words}]"
        )
    return doc


@stage(StageName.gemini)
def run_gemini(job: Job, ctx: StageContext) -> None:
    cfg = ctx.config
    g = cfg.gemini
    system = g.system_prompt.format(
        min_words=cfg.timing.min_words,
        max_words=cfg.timing.max_words,
        writer=job.writer,
        desk=job.desk,
    )
    base_user = f"Desk: {job.desk}\nWriter: {job.writer}\nTopics:\n{job.topics}"

    last_err: Exception | None = None
    user = base_user
    doc: ScriptDoc | None = None
    for _ in range(max(g.max_retries, 1)):
        raw = ctx.clients.gemini.generate_json(g.model, system, user, g.temperature)
        try:
            doc = validate_script(raw, cfg.timing)
            break
        except ScriptValidationError as e:
            last_err = e
            user = (
                f"{base_user}\n\nYour previous response was rejected: {e}\n"
                "Return corrected JSON only, matching the schema exactly."
            )
    if doc is None:
        raise RuntimeError(
            f"Gemini failed validation after {g.max_retries} attempts: {last_err}"
        )

    key = f"jobs/{job.id}/script.json"
    put_json(ctx.storage, key, doc.model_dump(mode="json"))
    job.script = doc
    job.beats = [BeatArtifact(beat_id=b.id) for b in doc.beats]
    job.stage(StageName.gemini).artifact_keys = [key]
