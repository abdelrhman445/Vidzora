"""
Final assembly — this is where the pipeline turns approved assets into one
publish-ready MP4:

  - Per-scene visual: AI image (Ken Burns zoom) OR stock video clip
    (center-cropped/looped to fit), always paired with its scene audio.
  - Crossfade transitions between every scene (no hard cuts).
  - Burned-in captions synced to each scene's voiceover.
  - Optional background music, mixed low under the voiceover.
  - Optional intro title card and outro (subscribe) card.

Uses MoviePy (ffmpeg under the hood) since we need per-clip duration
control, compositing (captions + bg bar) and simple transitions without
hand-rolling ffmpeg filter graphs.
"""
from __future__ import annotations

from pathlib import Path

from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    afx,
    concatenate_videoclips,
    vfx,
)

from src.config.constants import MediaType
from src.config.settings import settings
from src.database.models.video import Scene
from src.services.subtitle_service import build_caption_clip
from src.utils.logger import logger

_SIZE = (settings.VIDEO_WIDTH, settings.VIDEO_HEIGHT)


def _image_visual(image_path: str, duration: float):
    """Static image with a subtle continuous zoom (Ken Burns effect)."""
    from moviepy import ImageClip

    clip = ImageClip(image_path).with_duration(duration)
    clip = clip.resized(lambda t: 1 + 0.04 * (t / max(duration, 0.01)))
    clip = clip.resized(height=_SIZE[1])
    return CompositeVideoClip([clip], size=_SIZE).with_duration(duration)


def _video_visual(video_path: str, duration: float):
    """Stock footage clip, center-cropped to frame and looped/trimmed to
    exactly match the scene's voiceover duration."""
    clip = VideoFileClip(video_path).without_audio()

    if clip.duration < duration:
        clip = clip.with_effects([vfx.Loop(duration=duration)])
    else:
        clip = clip.subclipped(0, duration)

    clip = clip.resized(height=_SIZE[1])
    if clip.w < _SIZE[0]:
        clip = clip.resized(width=_SIZE[0])
    clip = clip.with_effects([vfx.Crop(x_center=clip.w / 2, y_center=clip.h / 2, width=_SIZE[0], height=_SIZE[1])])

    return CompositeVideoClip([clip], size=_SIZE).with_duration(duration)


def _build_scene_clip(scene: Scene):
    if scene.media_type == MediaType.VIDEO and scene.video_path:
        visual = _video_visual(scene.video_path, scene.audio_duration_sec)
    else:
        visual = _image_visual(scene.image_path, scene.audio_duration_sec)

    audio = AudioFileClip(scene.audio_path)
    visual = visual.with_audio(audio)

    if settings.ENABLE_SUBTITLES:
        caption = build_caption_clip(scene.voiceover_text, scene.audio_duration_sec, *_SIZE)
        visual = CompositeVideoClip([visual, caption], size=_SIZE).with_duration(scene.audio_duration_sec)

    return visual


def _title_card(text: str, duration: float):
    bg = ColorClip(size=_SIZE, color=(10, 10, 10)).with_duration(duration)
    title = (
        TextClip(
            text=text,
            font=settings.resolved_font_path,
            font_size=int(_SIZE[0] * 0.09),
            color="white",
            size=(int(_SIZE[0] * 0.85), None),
            method="caption",
            text_align="center",
        )
        .with_duration(duration)
        .with_position("center")
    )
    return CompositeVideoClip([bg, title], size=_SIZE).with_duration(duration)


def _apply_crossfades(clips: list):
    """Overlapping fade in/out on every clip, concatenated with negative
    padding so consecutive scenes visually dissolve into each other instead
    of hard-cutting."""
    fade = settings.CROSSFADE_DURATION_SEC
    if fade <= 0 or len(clips) < 2:
        return concatenate_videoclips(clips, method="compose")

    faded = []
    for i, clip in enumerate(clips):
        c = clip
        if i > 0:
            c = c.with_effects([vfx.CrossFadeIn(fade)])
        if i < len(clips) - 1:
            c = c.with_effects([vfx.CrossFadeOut(fade)])
        faded.append(c)

    return concatenate_videoclips(faded, method="compose", padding=-fade)


def _mix_background_music(final_clip):
    music_path = settings.BACKGROUND_MUSIC_PATH
    if not music_path or not Path(music_path).exists():
        return final_clip

    music = AudioFileClip(music_path).with_effects([afx.MultiplyVolume(settings.BACKGROUND_MUSIC_VOLUME)])
    if music.duration < final_clip.duration:
        music = music.with_effects([afx.AudioLoop(duration=final_clip.duration)])
    else:
        music = music.subclipped(0, final_clip.duration)

    mixed_audio = CompositeAudioClip([final_clip.audio, music])
    return final_clip.with_audio(mixed_audio)


def render_video(scenes: list[Scene], output_path: Path, title: str | None = None) -> Path:
    scene_clips = []
    all_clips_to_close = []

    try:
        if settings.ENABLE_INTRO_CARD and title:
            intro = _title_card(title, settings.INTRO_OUTRO_DURATION_SEC)
            scene_clips.append(intro)
            all_clips_to_close.append(intro)

        for scene in scenes:
            if not scene.audio_path or not scene.audio_duration_sec:
                raise ValueError(f"Scene {scene.scene_number} is missing audio")
            if scene.media_type == MediaType.IMAGE and not scene.image_path:
                raise ValueError(f"Scene {scene.scene_number} is missing its image")
            if scene.media_type == MediaType.VIDEO and not scene.video_path:
                raise ValueError(f"Scene {scene.scene_number} is missing its video clip")

            clip = _build_scene_clip(scene)
            scene_clips.append(clip)
            all_clips_to_close.append(clip)

        if settings.ENABLE_OUTRO_CARD:
            outro = _title_card(settings.OUTRO_TEXT, settings.INTRO_OUTRO_DURATION_SEC)
            scene_clips.append(outro)
            all_clips_to_close.append(outro)

        final = _apply_crossfades(scene_clips)
        final = _mix_background_music(final)

        final.write_videofile(
            str(output_path),
            fps=settings.VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            logger=None,
        )
        logger.info(f"Rendered final video -> {output_path}")
        return output_path
    finally:
        for c in all_clips_to_close:
            try:
                c.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass
