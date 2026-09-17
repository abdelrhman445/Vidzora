"""
Gemini-backed script generation & structuring.

Two entry points:
  - generate_script()      : AI writes the script from a topic (creative).
  - structure_custom_script(): user already wrote the script — Gemini only
    segments it into scenes and writes image prompts. It must NEVER alter
    the user's wording, since the whole point of "bring your own script"
    is that the voiceover matches exactly what they wrote.

Both share a JSON schema so the rest of the pipeline (TTS, images, render)
doesn't care which path produced the scenes.
"""
from __future__ import annotations

import json

from google import genai
from google.genai import types

from src.config.settings import settings
from src.utils.logger import logger

_SCENE_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "scene_number": {"type": "INTEGER"},
        "voiceover_text": {"type": "STRING"},
        "image_prompt": {"type": "STRING"},
        "visual_type": {
            "type": "STRING",
            "enum": ["image", "video"],
            "description": (
                "'video' if this beat is about motion/action/a real place or "
                "event that a short stock clip could depict; 'image' for "
                "conceptual, abstract, or illustrative beats better suited "
                "to a generated still."
            ),
        },
    },
    "required": ["scene_number", "voiceover_text", "image_prompt", "visual_type"],
}

_SCRIPT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "scenes": {"type": "ARRAY", "items": _SCENE_ITEM_SCHEMA},
    },
    "required": ["title", "scenes"],
}

_GENERATE_SYSTEM_PROMPT = (
    "You are a professional short-form video scriptwriter. Given a topic, "
    "produce a concise, engaging video script broken into 5-8 scenes. "
    "Each scene needs: a short voiceover line (1-2 sentences, natural spoken "
    "tone), a vivid text-to-image prompt (in English, visually descriptive, "
    "no text-in-image requests) that illustrates that line, and a visual_type "
    "('image' or 'video') indicating which would depict it better. "
    "Keep scene_number sequential starting at 1."
)

_STRUCTURE_SYSTEM_PROMPT = (
    "You are given a video script written by the user, verbatim below. "
    "Your ONLY job is to split it into scenes and, for each scene, write a "
    "vivid English text-to-image prompt plus a visual_type ('image' or "
    "'video'). "
    "CRITICAL: copy each scene's voiceover_text EXACTLY as written in the "
    "source — do not rewrite, summarize, translate, correct grammar, or add "
    "a single word. Split only at natural sentence/paragraph boundaries. "
    "Keep scene_number sequential starting at 1. Also invent a short title "
    "that describes the script."
)


def _call_gemini(system_prompt: str, user_content: str) -> dict:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=_SCRIPT_SCHEMA,
            temperature=0.8,
        ),
    )

    try:
        data = json.loads(response.text)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error(f"Gemini returned invalid JSON: {response.text!r}")
        raise ValueError("Script generation failed: model did not return valid JSON") from exc

    if not data.get("scenes"):
        raise ValueError("Script generation failed: no scenes returned")

    if not settings.ENABLE_STOCK_FOOTAGE:
        for scene in data["scenes"]:
            scene["visual_type"] = "image"

    return data


def generate_script(topic_prompt: str) -> dict:
    """AI writes the script from scratch. Synchronous — safe from Celery."""
    return _call_gemini(_GENERATE_SYSTEM_PROMPT, f"Topic: {topic_prompt}")


def structure_custom_script(raw_script: str) -> dict:
    """User-provided script -> scenes + image prompts, wording untouched."""
    return _call_gemini(_STRUCTURE_SYSTEM_PROMPT, raw_script)
