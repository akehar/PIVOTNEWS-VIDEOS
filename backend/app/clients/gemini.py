from __future__ import annotations

import json
import os
import tempfile


class GeminiClient:
    """Gemini with structured JSON output.

    Auth precedence: if `api_key` is set, use Google AI Studio. Otherwise
    fall back to Vertex AI using a service-account JSON (the
    GOOGLE_APPLICATION_CREDENTIALS_JSON env var). The service-account file
    is materialized once on first use and pointed at via the standard
    GOOGLE_APPLICATION_CREDENTIALS env var.
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        service_account_json: str = "",
        gcp_project: str = "",
        gcp_location: str = "us-central1",
    ) -> None:
        self.api_key = api_key
        self.service_account_json = service_account_json
        self.gcp_project = gcp_project
        self.gcp_location = gcp_location
        self._vertex_ready = False

    def _ensure_vertex_creds(self) -> tuple[str, str]:
        """Write the JSON to disk for ADC and return (project, location)."""
        if not self.service_account_json:
            raise RuntimeError(
                "no Gemini auth configured: set GEMINI_API_KEY or "
                "GOOGLE_APPLICATION_CREDENTIALS_JSON"
            )
        if not self._vertex_ready:
            data = json.loads(self.service_account_json)
            fd, path = tempfile.mkstemp(suffix=".json", prefix="gcp_sa_")
            with os.fdopen(fd, "w") as f:
                f.write(self.service_account_json)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
            self._vertex_project = self.gcp_project or data.get("project_id", "")
            if not self._vertex_project:
                raise RuntimeError("Vertex needs a GCP project (set GCP_PROJECT)")
            self._vertex_ready = True
        return self._vertex_project, self.gcp_location

    def _client(self):
        from google import genai

        if self.api_key:
            return genai.Client(api_key=self.api_key)
        project, location = self._ensure_vertex_creds()
        return genai.Client(vertexai=True, project=project, location=location)

    def generate_json(
        self, model: str, system_prompt: str, user_prompt: str, temperature: float
    ) -> str:
        from google.genai import types

        resp = self._client().models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        return resp.text or ""
