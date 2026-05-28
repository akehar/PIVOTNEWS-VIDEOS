from __future__ import annotations


class GeminiClient:
    """Google Gemini with structured JSON output (response_mime_type)."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def generate_json(
        self, model: str, system_prompt: str, user_prompt: str, temperature: float
    ) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        resp = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        return resp.text or ""
