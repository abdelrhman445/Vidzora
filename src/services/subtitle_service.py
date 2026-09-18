"""
Burned-in captions. Builds a styled TextClip (semi-transparent bar + bold
centered text near the bottom-third) sized/timed to a single scene, so the
render service just has to overlay one clip per scene.
"""
from __future__ import annotations

from moviepy import ColorClip, CompositeVideoClip, TextClip

from src.config.settings import settings


def build_caption_clip(text: str, duration: float, video_w: int, video_h: int):
    text_clip = (
        TextClip(
            text=text,
            font=settings.resolved_font_path,
            font_size=settings.SUBTITLE_FONT_SIZE,
            color="white",
            stroke_color="black",
            stroke_width=2,
            size=(int(video_w * 0.88), None),
            method="caption",
            text_align="center",
        )
        .with_duration(duration)
    )

    bar_height = text_clip.h + 40
    bg_bar = (
        ColorClip(size=(video_w, bar_height), color=(0, 0, 0))
        .with_opacity(0.45)
        .with_duration(duration)
    )

    bottom_margin = int(video_h * 0.08)
    y_position = video_h - bottom_margin - bar_height

    return CompositeVideoClip(
        [
            bg_bar.with_position(("center", y_position)),
            text_clip.with_position(("center", y_position + 20)),
        ],
        size=(video_w, video_h),
    ).with_duration(duration)
