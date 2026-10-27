"""Shared pytest fixtures for video-cut CLI tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture()
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def fixture_video(tmp_path: Path) -> Path:
    """Generate a small real fixture video: 10s color bars + sine tone."""
    video = tmp_path / "fixture.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=10:size=320x240:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=10",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    return video


def _ffprobe(path: Path, args: list[str]) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", *args, "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def ffprobe_audio_stream(path: Path) -> dict[str, str]:
    """Return the first audio stream's metadata for an output file."""
    data = _ffprobe(
        path,
        [
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels",
        ],
    )
    return data["streams"][0]


def ffprobe_video_stream(path: Path) -> dict:
    """Return the first video stream's metadata for an output file."""
    data = _ffprobe(
        path,
        [
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,pix_fmt,r_frame_rate,width,height",
        ],
    )
    return data["streams"][0]


def ffprobe_duration(path: Path) -> float:
    """Return the container duration of an output file in seconds."""
    data = _ffprobe(path, ["-show_entries", "format=duration"])
    return float(data["format"]["duration"])


def write_highlights(output_dir: Path, video_stem: str, highlights: list[dict]) -> Path:
    """Write a highlights.json into the artifact directory for a video."""
    target_dir = output_dir / video_stem
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "highlights.json"
    path.write_text(json.dumps(highlights, ensure_ascii=False), encoding="utf-8")
    return path
