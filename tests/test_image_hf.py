from pathlib import Path

import httpx
import pytest

from ytvg.config import Settings
from ytvg.domain.exceptions import ExternalServiceError
from ytvg.infrastructure.ai import image_pollinations


class FakeAsyncClient:
    response = httpx.Response(200, content=b"fake-image")
    requests: list[tuple[str, dict, dict]] = []

    def __init__(self, **_: object) -> None:
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def get(self, url: str, *, params: dict, headers: dict) -> httpx.Response:
        self.requests.append((url, params, headers))
        return self.response


@pytest.mark.asyncio
async def test_generate_uses_pollinations_and_writes_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    FakeAsyncClient.requests.clear()
    monkeypatch.setattr(image_pollinations.httpx, "AsyncClient", FakeAsyncClient)

    generator = image_pollinations.PollinationsImageGenerator(
        Settings(
            pollinations_api_key="token",
            pollinations_image_model="nanobanana-2",
        )
    )
    output_path = tmp_path / "scene.png"

    result = await generator.generate(prompt="A bright city street", output_path=str(output_path))

    assert result == str(output_path)
    assert output_path.read_bytes() == b"fake-image"
    url, params, headers = FakeAsyncClient.requests[0]
    assert url.endswith("/A%20bright%20city%20street")
    assert params == {"model": "nanobanana-2", "nologo": "true"}
    assert headers == {"Authorization": "Bearer token"}


@pytest.mark.asyncio
async def test_generate_does_not_retry_when_credits_are_exhausted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    FakeAsyncClient.requests.clear()
    FakeAsyncClient.response = httpx.Response(402, content=b"credits exhausted")
    monkeypatch.setattr(image_pollinations.httpx, "AsyncClient", FakeAsyncClient)

    generator = image_pollinations.PollinationsImageGenerator(
        Settings(pollinations_api_key="token")
    )

    with pytest.raises(ExternalServiceError, match="no available credits"):
        await generator.generate(
            prompt="A bright city street", output_path=str(tmp_path / "scene.png")
        )

    assert len(FakeAsyncClient.requests) == 1
    FakeAsyncClient.response = httpx.Response(200, content=b"fake-image")