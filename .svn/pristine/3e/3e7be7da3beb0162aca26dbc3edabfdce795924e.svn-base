"""Tests for `video-cut extract-audio` at the CLI seam.

ffmpeg is real in these tests; the fixture video is generated
programmatically (10s color bars + sine tone).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from typer.testing import CliRunner

from tests.conftest import ffprobe_audio_stream
from video_cut.cli import app


def test_extract_audio_produces_16khz_mono_m4a(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"

    result = cli_runner.invoke(
        app, ["extract-audio", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code == 0, result.output
    audio = output_dir / fixture_video.stem / "audio.m4a"
    assert audio.exists()

    stream = ffprobe_audio_stream(audio)
    assert stream["sample_rate"] == "16000"
    assert stream["channels"] == 1
    assert stream["codec_name"] == "aac"


def test_extract_audio_skips_when_artifact_exists(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    args = ["extract-audio", str(fixture_video), "--output-dir", str(output_dir)]

    first = cli_runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    audio = output_dir / fixture_video.stem / "audio.m4a"
    first_mtime = audio.stat().st_mtime_ns

    time.sleep(0.01)
    second = cli_runner.invoke(app, args)

    assert second.exit_code == 0, second.output
    assert "skip" in second.output.lower()
    assert audio.stat().st_mtime_ns == first_mtime


def test_extract_audio_force_regenerates_artifact(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    args = ["extract-audio", str(fixture_video), "--output-dir", str(output_dir)]

    first = cli_runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    audio = output_dir / fixture_video.stem / "audio.m4a"
    first_mtime = audio.stat().st_mtime_ns

    time.sleep(0.01)
    forced = cli_runner.invoke(app, [*args, "--force"])

    assert forced.exit_code == 0, forced.output
    assert audio.stat().st_mtime_ns > first_mtime


def test_extract_audio_without_config_does_not_require_cloud_keys(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path, monkeypatch
) -> None:
    """extract-audio is purely local; cloud keys must NOT be required for it."""
    for key in (
        "VIDEO_CUT_DASHSCOPE_API_KEY",
        "VIDEO_CUT_OSS_BUCKET",
        "VIDEO_CUT_OSS_ENDPOINT",
        "VIDEO_CUT_OSS_ACCESS_KEY_ID",
        "VIDEO_CUT_OSS_ACCESS_KEY_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)

    result = cli_runner.invoke(
        app,
        [
            "extract-audio",
            str(fixture_video),
            "--output-dir",
            str(tmp_path / "output"),
        ],
    )

    assert result.exit_code == 0, result.output
