"""
Image generation, provider-agnostic behind IMAGE_PROVIDER.
Supports Hugging Face Inference API (default, cheapest/free-tier friendly)
and Leonardo AI (higher quality, paid). Both are plain sync HTTP calls,
so they run directly inside a Celery task with no event-loop juggling.
"""
from __future__ import annotations

import time
from pathlib import Path

import requests

from src.config.settings import settings
from src.utils.logger import logger

_HF_URL_TMPL = "https://router.huggingface.co/hf-inference/models/{model}"
_POLLINATIONS_URL_TMPL = "https://gen.pollinations.ai/image/{prompt}"


def _generate_huggingface(prompt: str, out_path: Path) -> None:
    url = _HF_URL_TMPL.format(model=settings.HUGGINGFACE_IMAGE_MODEL)
    headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"}

    # HF inference endpoints cold-start; retry on 503 ("model loading").
    for attempt in range(5):
        resp = requests.post(url, headers=headers, json={"inputs": prompt}, timeout=120)
        if resp.status_code == 200:
            out_path.write_bytes(resp.content)
            return
        if resp.status_code == 503:
            wait = resp.json().get("estimated_time", 20)
            logger.info(f"HF model loading, retrying in {wait:.0f}s (attempt {attempt + 1}/5)")
            time.sleep(min(wait, 30))
            continue
        resp.raise_for_status()

    raise RuntimeError(f"Hugging Face image generation failed after retries for prompt: {prompt!r}")


def _generate_pollinations(prompt: str, out_path: Path) -> None:
    import urllib.parse

    url = _POLLINATIONS_URL_TMPL.format(prompt=urllib.parse.quote(prompt))
    headers = {"Authorization": f"Bearer {settings.POLLINATIONS_API_KEY}"}
    params = {
        "model": settings.POLLINATIONS_IMAGE_MODEL,
        "width": settings.VIDEO_WIDTH,
        "height": settings.VIDEO_HEIGHT,
        "nologo": "true",
    }

    resp = requests.get(url, headers=headers, params=params, timeout=120)
    if resp.status_code == 200:
        out_path.write_bytes(resp.content)
        return
    resp.raise_for_status()


def _generate_leonardo(prompt: str, out_path: Path) -> None:
    headers = {
        "Authorization": f"Bearer {settings.LEONARDO_API_KEY}",
        "Content-Type": "application/json",
    }
    base = "https://cloud.leonardo.ai/api/rest/v1"

    create_resp = requests.post(
        f"{base}/generations",
        headers=headers,
        json={
            "prompt": prompt,
            "modelId": settings.LEONARDO_MODEL_ID or None,
            "width": settings.VIDEO_WIDTH,
            "height": settings.VIDEO_HEIGHT,
            "num_images": 1,
        },
        timeout=30,
    )
    create_resp.raise_for_status()
    generation_id = create_resp.json()["sdGenerationJob"]["generationId"]

    for _ in range(30):
        time.sleep(4)
        status_resp = requests.get(f"{base}/generations/{generation_id}", headers=headers, timeout=30)
        status_resp.raise_for_status()
        gen = status_resp.json()["generations_by_pk"]
        if gen["status"] == "COMPLETE":
            image_url = gen["generated_images"][0]["url"]
            img_resp = requests.get(image_url, timeout=60)
            img_resp.raise_for_status()
            out_path.write_bytes(img_resp.content)
            return
        if gen["status"] == "FAILED":
            raise RuntimeError(f"Leonardo generation failed for prompt: {prompt!r}")

    raise TimeoutError(f"Leonardo generation timed out for prompt: {prompt!r}")


def generate_image(prompt: str, out_path: Path) -> None:
    if settings.IMAGE_PROVIDER == "leonardo":
        _generate_leonardo(prompt, out_path)
    elif settings.IMAGE_PROVIDER == "pollinations":
        _generate_pollinations(prompt, out_path)
    else:
        _generate_huggingface(prompt, out_path)
