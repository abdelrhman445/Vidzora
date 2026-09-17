"""
Stock B-roll video clips via the Pexels API (free tier, no watermarks,
commercially usable). Used for scenes Gemini tags as `visual_type: video`
so the final render can mix real footage with AI-generated stills.
"""
from __future__ import annotations

from pathlib import Path

import requests

from src.config.settings import settings

_SEARCH_URL = "https://api.pexels.com/videos/search"


def _pick_best_file(video: dict, target_w: int, target_h: int) -> dict | None:
    """Prefer a file already close to our target resolution/orientation to
    minimize upscaling artifacts in the final render."""
    files = video.get("video_files", [])
    if not files:
        return None

    target_portrait = target_h >= target_w

    def score(f: dict) -> tuple[int, int]:
        w, h = f.get("width") or 0, f.get("height") or 0
        is_portrait = h >= w
        orientation_match = 0 if is_portrait == target_portrait else 1
        res_gap = abs((w or 0) - target_w) + abs((h or 0) - target_h)
        return (orientation_match, res_gap)

    return sorted(files, key=score)[0]


def fetch_stock_clip(query: str, out_path: Path, min_duration_sec: float) -> bool:
    """
    Downloads a Pexels clip matching `query` that is at least
    `min_duration_sec` long (so it can cover the scene's voiceover without
    looping). Returns False (caller should fall back to an AI image) if no
    suitable clip is found rather than raising — stock footage availability
    is inherently unpredictable.
    """
    if not settings.PEXELS_API_KEY:
        return False

    headers = {"Authorization": settings.PEXELS_API_KEY}
    params = {"query": query, "per_page": 10, "orientation": "portrait" if settings.VIDEO_HEIGHT >= settings.VIDEO_WIDTH else "landscape"}

    resp = requests.get(_SEARCH_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    videos = resp.json().get("videos", [])

    candidates = [v for v in videos if v.get("duration", 0) >= min_duration_sec]
    if not candidates:
        candidates = videos  # we'll loop it in the render step if too short

    for video in candidates:
        best_file = _pick_best_file(video, settings.VIDEO_WIDTH, settings.VIDEO_HEIGHT)
        if not best_file:
            continue

        video_resp = requests.get(best_file["link"], timeout=120)
        if video_resp.status_code == 200:
            out_path.write_bytes(video_resp.content)
            return True

    return False
