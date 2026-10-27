"""Audio extraction via ffmpeg."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

AUDIO_SAMPLE_RATE_HZ = 16000
AUDIO_CHANNELS = 1


def probe_duration(video_path: Path) -> float | None:
    """视频时长（秒）；ffprobe 失败或输出异常返回 None（UI 显示为未知）。"""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    try:
        duration = json.loads(result.stdout)["format"]["duration"]
    except (KeyError, json.JSONDecodeError, TypeError):
        return None
    try:
        return float(duration)
    except ValueError:
        return None


def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Extract audio from a video as 16kHz mono AAC (.m4a), optimized for ASR."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            str(AUDIO_CHANNELS),
            "-ar",
            str(AUDIO_SAMPLE_RATE_HZ),
            "-c:a",
            "aac",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
