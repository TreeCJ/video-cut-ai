"""Tests for `video-cut cut` at the CLI seam.

ffmpeg is real in these tests: the fixture video is generated
programmatically (10s color bars + sine tone) and highlights.json
is handwritten. Assertions use ffprobe on the produced artifacts.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from typer.testing import CliRunner

from tests.conftest import (
    ffprobe_audio_stream,
    ffprobe_duration,
    ffprobe_video_stream,
    write_highlights,
)
from video_cut.cli import app

FRAME_TOLERANCE_S = 1.0 / 30.0
MERGE_TOLERANCE_S = 0.1

HIGHLIGHTS = [
    {
        "title": "opening-hook",
        "reason": "test fixture segment one",
        "quote": "unused in ticket 02",
        "start": 1.0,
        "end": 3.5,
    },
    {
        "title": "second beat",
        "reason": "test fixture segment two",
        "quote": "unused in ticket 02",
        "start": 5.0,
        "end": 7.0,
    },
]


def _run_cut(cli_runner: CliRunner, video: Path, output_dir: Path, *extra: str):
    return cli_runner.invoke(
        app, ["cut", str(video), "--output-dir", str(output_dir), *extra]
    )


def _write_default_highlights(output_dir: Path, video: Path) -> None:
    write_highlights(output_dir, video.stem, HIGHLIGHTS)


def test_cut_produces_one_clip_per_highlight_with_duration_and_uniform_params(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _write_default_highlights(output_dir, fixture_video)

    result = _run_cut(cli_runner, fixture_video, output_dir)

    assert result.exit_code == 0, result.output
    clips_dir = output_dir / fixture_video.stem / "clips"
    clip_paths = sorted(clips_dir.glob("*.mp4"))
    assert [p.name for p in clip_paths] == [
        "01-opening-hook.mp4",
        "02-second beat.mp4",
    ]

    for clip, highlight in zip(clip_paths, HIGHLIGHTS):
        duration = ffprobe_duration(clip)
        assert abs(duration - (highlight["end"] - highlight["start"])) <= FRAME_TOLERANCE_S

        video_stream = ffprobe_video_stream(clip)
        assert video_stream["codec_name"] == "h264"
        assert video_stream["pix_fmt"] == "yuv420p"
        assert video_stream["r_frame_rate"] == "30/1"
        assert video_stream["width"] <= 1920
        assert video_stream["height"] <= 1080

        audio_stream = ffprobe_audio_stream(clip)
        assert audio_stream["codec_name"] == "aac"
        assert audio_stream["sample_rate"] == "48000"
        assert audio_stream["channels"] == 2


def test_cut_merges_clips_into_merged_mp4_without_reencode(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _write_default_highlights(output_dir, fixture_video)

    result = _run_cut(cli_runner, fixture_video, output_dir)

    assert result.exit_code == 0, result.output
    target_dir = output_dir / fixture_video.stem
    merged = target_dir / "merged.mp4"
    assert merged.exists()

    clip_paths = sorted((target_dir / "clips").glob("*.mp4"))
    expected = sum(ffprobe_duration(clip) for clip in clip_paths)
    assert abs(ffprobe_duration(merged) - expected) <= MERGE_TOLERANCE_S

    # Stream-copy merge: the merged file's streams must carry the same
    # encoding parameters as each clip's (no re-encode happened).
    merged_video = ffprobe_video_stream(merged)
    merged_audio = ffprobe_audio_stream(merged)
    for clip in clip_paths:
        assert ffprobe_video_stream(clip) == merged_video
        assert ffprobe_audio_stream(clip) == merged_audio


def test_cut_skips_existing_artifacts_and_force_reruns(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _write_default_highlights(output_dir, fixture_video)
    args = [str(fixture_video), "--output-dir", str(output_dir)]

    first = _run_cut(cli_runner, fixture_video, output_dir)
    assert first.exit_code == 0, first.output

    target_dir = output_dir / fixture_video.stem
    clips = sorted((target_dir / "clips").glob("*.mp4"))
    merged = target_dir / "merged.mp4"
    mtimes = {p: p.stat().st_mtime_ns for p in [*clips, merged]}

    time.sleep(0.01)
    second = _run_cut(cli_runner, fixture_video, output_dir)
    assert second.exit_code == 0, second.output
    assert "skip" in second.output.lower()
    for path, mtime in mtimes.items():
        assert path.stat().st_mtime_ns == mtime

    time.sleep(0.01)
    forced = _run_cut(cli_runner, fixture_video, output_dir, "--force")
    assert forced.exit_code == 0, forced.output
    for path, mtime in mtimes.items():
        assert path.stat().st_mtime_ns > mtime


def test_cut_fails_with_clear_error_when_highlights_missing(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    result = _run_cut(cli_runner, fixture_video, tmp_path / "output")

    assert result.exit_code != 0
    assert "highlights.json" in result.output


def test_cut_runs_slice_jobs_with_bounded_concurrency(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    """--concurrency 1 forces serial slicing; default runs jobs in parallel.

    A serial run must produce exactly the same artifacts as a parallel one —
    the option exists to bound the ffmpeg process pool (default: CPU count).
    """
    output_dir = tmp_path / "output"
    _write_default_highlights(output_dir, fixture_video)

    serial = _run_cut(cli_runner, fixture_video, output_dir, "--concurrency", "1")
    assert serial.exit_code == 0, serial.output

    target_dir = output_dir / fixture_video.stem
    clip_paths = sorted((target_dir / "clips").glob("*.mp4"))
    assert len(clip_paths) == len(HIGHLIGHTS)
    serial_durations = [ffprobe_duration(p) for p in clip_paths]

    parallel = _run_cut(cli_runner, fixture_video, output_dir, "--force")
    assert parallel.exit_code == 0, parallel.output
    assert [ffprobe_duration(p) for p in clip_paths] == serial_durations


def test_cut_rejects_invalid_highlights_json(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    target_dir = output_dir / fixture_video.stem
    target_dir.mkdir(parents=True)
    (target_dir / "highlights.json").write_text(
        json.dumps([{"title": "bad", "start": 5.0, "end": 1.0}]),
        encoding="utf-8",
    )

    result = _run_cut(cli_runner, fixture_video, output_dir)

    assert result.exit_code != 0
    assert "invalid" in result.output.lower() or "end <= start" in result.output
