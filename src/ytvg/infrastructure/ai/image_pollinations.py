from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ytvg.config import Settings, get_settings
from ytvg.domain.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_POLLINATIONS_URL = "https://gen.pollinations.ai/image"


class _RetryablePollinationsError(Exception):
    pass


class PollinationsImageGenerator:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

        if not self._settings.pollinations_api_key:
            raise ExternalServiceError("POLLINATIONS_API_KEY is not configured")

    @retry(
        retry=retry_if_exception_type(_RetryablePollinationsError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=20),
        reraise=True,
    )
    async def _request_image(self, *, prompt: str, model: str) -> bytes:
        headers = {"Authorization": f"Bearer {self._settings.pollinations_api_key}"}
        url = f"{_POLLINATIONS_URL}/{quote(prompt, safe='')}"
        params = {"model": model, "nologo": "true"}

        try:
            async with httpx.AsyncClient(timeout=self._settings.image_timeout_sec) as client:
                response = await client.get(url, params=params, headers=headers)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise _RetryablePollinationsError(str(exc)) from exc

        if response.status_code == 402:
            raise ExternalServiceError(
                "Pollinations image generation has no available credits"
            )
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise _RetryablePollinationsError(
                f"Pollinations returned HTTP {response.status_code}"
            )
        if response.is_error:
            raise ExternalServiceError(
                f"Pollinations image generation failed: HTTP {response.status_code}"
            )
        if not response.content:
            raise ExternalServiceError("Pollinations returned an empty image")
        return response.content

    async def generate(self, *, prompt: str, output_path: str) -> str:
        if not prompt or not prompt.strip():
            raise ExternalServiceError("Image prompt is empty")

        model = self._settings.pollinations_image_model
        if not model:
            raise ExternalServiceError("IMAGE_MODEL is not configured")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Generating image with Pollinations: model=%s", model)

        try:
            image = await self._request_image(prompt=prompt.strip(), model=model)
        except _RetryablePollinationsError as exc:
            fallback_model = self._settings.image_fallback_model.strip()
            if not fallback_model or fallback_model == model:
                raise ExternalServiceError(
                    f"Pollinations image generation failed after retries: {exc}"
                ) from exc
            logger.warning("Retrying Pollinations with fallback model=%s", fallback_model)
            try:
                image = await self._request_image(
                    prompt=prompt.strip(), model=fallback_model
                )
            except _RetryablePollinationsError as fallback_exc:
                raise ExternalServiceError(
                    f"Pollinations image generation failed after fallback: {fallback_exc}"
                ) from fallback_exc
        except ExternalServiceError:
            raise
        except Exception as exc:
            logger.exception("Pollinations image generation failed: %s", exc)
            raise ExternalServiceError(f"Pollinations image generation failed: {exc}") from exc

        await asyncio.to_thread(output.write_bytes, image)
        if not output.exists() or output.stat().st_size == 0:
            raise ExternalServiceError("Generated image is empty")

        logger.info("Wrote image %s (%d bytes)", output, output.stat().st_size)
        return str(output)