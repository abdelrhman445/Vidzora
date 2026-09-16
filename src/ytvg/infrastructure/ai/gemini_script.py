from __future__ import annotations

import json
import logging
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ytvg.config import Settings, get_settings
from ytvg.domain.entities import Script
from ytvg.domain.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_SCRIPT_SYSTEM = """You are a YouTube short-form video scriptwriter.
Return ONLY valid JSON with this exact schema:
{
  "title": "string",
  "description": "string",
  "scenes": [
    {
      "index": 1,
      "voiceover": "spoken narration for this scene",
      "image_prompt": "detailed visual prompt for an image model",
      "duration_hint_sec": 8
    }
  ]
}
Rules:
- 4 to 8 scenes.
- Voiceover must be natural spoken English, 1-3 sentences per scene.
- Image prompts must be self-contained, cinematic, no text overlays.
"""


class GeminiScriptGenerator:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    async def generate(self, prompt: str) -> Script:
        if not self._settings.gemini_api_key:
            raise ExternalServiceError("GEMINI_API_KEY is not configured")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._settings.gemini_model}:generateContent"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{_SCRIPT_SYSTEM}\n\nTopic: {prompt}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "responseMimeType": "application/json",
            },
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                url,
                params={"key": self._settings.gemini_api_key},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise ExternalServiceError(f"Unexpected Gemini payload: {data}") from exc

        return Script.model_validate(_parse_json(text))


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ExternalServiceError(f"Gemini did not return JSON: {text[:400]}")
        return json.loads(match.group(0))
