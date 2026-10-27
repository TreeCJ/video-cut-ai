"""End-to-end tests for the run command at the CLI seam.

External services are replaced by fakes injected via env config (same pattern
as test_transcribe / test_analyze):
- VIDEO_CUT_ASR_ENGINE_FAKE: canned engine payload (shape locked to Transcript)
- VIDEO_CUT_LLM_PROVIDER_FAKE: canned highlight list (shape locked to Highlight)
- VIDEO_CUT_OSS_FAKE_DIR: local-directory stand-in for OSS that records deletes
- _VIDEO_CUT_FAKE_ENGINE_URLS_FILE / _VIDEO_CUT_FAKE_PROVIDER_CALLS_FILE:
  fake call counters used to assert skip/force behavior

ffmpeg is never faked: clips and merged.mp4 are really produced from the
fixture video. No test touches the network.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from conftest import ffprobe_duration, write_highlights
from typer.testing import CliRunner

from video_cut.cli import app

CLOUD_KEYS = (
    "VIDEO_CUT_DASHSCOPE_API_KEY",
    "VIDEO_CUT_OSS_BUCKET",
    "VIDEO_CUT_OSS_ENDPOINT",
    "VIDEO_CUT_OSS_ACCESS_KEY_ID",
    "VIDEO_CUT_OSS_ACCESS_KEY_SECRET",
)

ENGINE_PAYLOAD = {
    "sentences": [
        {"begin_time": 0.5, "end_time": 2.0, "text": "大家好，欢迎来到本期视频。"},
        {"begin_time": 2.5, "end_time": 5.0, "text": "其实90%的人都搞错了。"},
        {"begin_time": 5.5, "end_time": 9.0, "text": "今天我们把这个问题讲透。"},
    ],
    "words": [
        {"begin_time": 0.5, "end_time": 0.8, "word": "大家"},
        {"begin_time": 2.5, "end_time": 2.8, "word": "其实"},
    ],
}

CANNED_HIGHLIGHTS = [
    {
        "title": "开场反转",
        "reason": "前30秒抛出反常识结论",
        "quote": "其实90%的人都搞错了。",
        "start": 2.5,
        "end": 5.0,
    },
    {
        "title": "收尾承诺",
        "reason": "信息密度高，预告全片价值",
        "quote": "今天我们把这个问题讲透。",
        "start": 5.5,
        "end": 9.0,
    },
]


@pytest.fixture()
def fake_all(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, Path]:
    """Scrub real cloud config, then inject fake Engine, Provider and OSS."""
    for key in CLOUD_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)  # isolate from any real .env in the repo root

    monkeypatch.setenv("VIDEO_CUT_DASHSCOPE_API_KEY", "fake-dashscope-key")
    monkeypatch.setenv("VIDEO_CUT_OSS_BUCKET", "fake-bucket")
    monkeypatch.setenv("VIDEO_CUT_OSS_ENDPOINT", "https://fake-oss.local")
    monkeypatch.setenv("VIDEO_CUT_OSS_ACCESS_KEY_ID", "fake-ak")
    monkeypatch.setenv("VIDEO_CUT_OSS_ACCESS_KEY_SECRET", "fake-sk")

    oss_dir = tmp_path / "fake-oss"
    engine_urls_file = tmp_path / "engine-urls.txt"
    provider_calls_file = tmp_path / "provider-calls.json"
    monkeypatch.setenv("VIDEO_CUT_OSS_FAKE_DIR", str(oss_dir))
    monkeypatch.setenv("_VIDEO_CUT_FAKE_ENGINE_URLS_FILE", str(engine_urls_file))
    monkeypatch.setenv("_VIDEO_CUT_FAKE_PROVIDER_CALLS_FILE", str(provider_calls_file))
    monkeypatch.setenv("VIDEO_CUT_ASR_ENGINE_FAKE", json.dumps(ENGINE_PAYLOAD))
    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps(CANNED_HIGHLIGHTS)
    )

    return {
        "oss_dir": oss_dir,
        "engine_urls_file": engine_urls_file,
        "provider_calls_file": provider_calls_file,
    }


def _engine_call_count(fakes: dict[str, Path]) -> int:
    urls_file = fakes["engine_urls_file"]
    if not urls_file.exists():
        return 0
    return len(urls_file.read_text(encoding="utf-8").splitlines())


def _provider_call_count(fakes: dict[str, Path]) -> int:
    calls_file = fakes["provider_calls_file"]
    if not calls_file.exists():
        return 0
    return len(json.loads(calls_file.read_text(encoding="utf-8")))


def _stage_transcript(output_dir: Path, video: Path) -> Path:
    target_dir = output_dir / video.stem
    target_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = target_dir / "transcript.json"
    transcript_path.write_text(
        json.dumps(ENGINE_PAYLOAD, ensure_ascii=False), encoding="utf-8"
    )
    return transcript_path


def test_run_auto_produces_clips_and_merged_end_to_end(
    cli_runner: CliRunner, fixture_video: Path, fake_all: dict[str, Path], tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"

    result = cli_runner.invoke(
        app,
        ["run", str(fixture_video), "--output-dir", str(output_dir), "--auto"],
    )

    assert result.exit_code == 0, result.output
    target_dir = output_dir / fixture_video.stem
    clips = sorted((target_dir / "clips").glob("*.mp4"))
    assert len(clips) == len(CANNED_HIGHLIGHTS)
    merged = target_dir / "merged.mp4"
    assert merged.exists()

    # Quotes match transcript sentences exactly. The gaps between fixture
    # sentences are 0.5s, so the adaptive buffer shrinks to half the gap
    # (0.25s) on each side where a neighbour exists; the first clip's head
    # and the last clip's tail keep the full 0.5s... except clip 2's tail
    # also faces a 0.5s gap. Clip 1: 2.5-0.25=2.25 to 5.0+0.25=5.25 → 3.0s.
    # Clip 2: 5.5-0.25=5.25 to 9.0+0.5 (no next sentence) = 9.5 → 4.25s.
    expected_durations = [3.0, 4.25]
    tolerance = 1 / 30  # one frame
    clip_durations = [ffprobe_duration(clip) for clip in clips]
    for actual, expected in zip(clip_durations, expected_durations):
        assert abs(actual - expected) < tolerance + 0.1
    merged_duration = ffprobe_duration(merged)
    assert abs(merged_duration - sum(clip_durations)) < tolerance + 0.1


def test_run_default_stops_after_analyze_then_cut_completes(
    cli_runner: CliRunner, fixture_video: Path, fake_all: dict[str, Path], tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    target_dir = output_dir / fixture_video.stem

    result = cli_runner.invoke(
        app, ["run", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code == 0, result.output
    # The human checkpoint: earlier artifacts exist, the highlight list is
    # printed for review, but nothing is cut yet.
    assert (target_dir / "audio.m4a").exists()
    assert (target_dir / "transcript.json").exists()
    assert (target_dir / "highlights.json").exists()
    for highlight in CANNED_HIGHLIGHTS:
        assert highlight["title"] in result.output
        assert highlight["reason"] in result.output
    assert "highlights.json" in result.output  # tells the user what to edit
    assert "cut" in result.output  # and how to continue
    assert not (target_dir / "clips").exists()
    assert not (target_dir / "merged.mp4").exists()

    result = cli_runner.invoke(
        app, ["cut", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code == 0, result.output
    clips = sorted((target_dir / "clips").glob("*.mp4"))
    assert len(clips) == len(CANNED_HIGHLIGHTS)
    assert (target_dir / "merged.mp4").exists()


def test_run_skips_transcribe_when_transcript_exists(
    cli_runner: CliRunner, fixture_video: Path, fake_all: dict[str, Path], tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)

    result = cli_runner.invoke(
        app,
        ["run", str(fixture_video), "--output-dir", str(output_dir), "--auto"],
    )

    assert result.exit_code == 0, result.output
    assert _engine_call_count(fake_all) == 0
    assert _provider_call_count(fake_all) == 1
    assert (output_dir / fixture_video.stem / "merged.mp4").exists()


def test_run_force_reruns_every_step(
    cli_runner: CliRunner, fixture_video: Path, fake_all: dict[str, Path], tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"

    first = cli_runner.invoke(
        app,
        ["run", str(fixture_video), "--output-dir", str(output_dir), "--auto"],
    )
    assert first.exit_code == 0, first.output
    assert _engine_call_count(fake_all) == 1
    assert _provider_call_count(fake_all) == 1

    # A second run without --force must reuse every artifact.
    again = cli_runner.invoke(
        app,
        ["run", str(fixture_video), "--output-dir", str(output_dir), "--auto"],
    )
    assert again.exit_code == 0, again.output
    assert _engine_call_count(fake_all) == 1
    assert _provider_call_count(fake_all) == 1

    # Mark every artifact so regeneration is detectable: the fake counters
    # reset per invocation, so --force is proven by artifacts being rewritten.
    target_dir = output_dir / fixture_video.stem
    artifacts = [
        target_dir / "audio.m4a",
        target_dir / "transcript.json",
        target_dir / "highlights.json",
        target_dir / "merged.mp4",
        *sorted((target_dir / "clips").glob("*.mp4")),
    ]
    marker = 1_000_000_000  # 2001-09-09, clearly older than any real write
    for artifact in artifacts:
        os.utime(artifact, (marker, marker))

    second = cli_runner.invoke(
        app,
        [
            "run",
            str(fixture_video),
            "--output-dir",
            str(output_dir),
            "--auto",
            "--force",
        ],
    )

    assert second.exit_code == 0, second.output
    for artifact in artifacts:
        assert artifact.exists()
        assert artifact.stat().st_mtime > marker, f"not regenerated: {artifact}"


def test_run_cleans_up_oss_object_after_transcribe(
    cli_runner: CliRunner, fixture_video: Path, fake_all: dict[str, Path], tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"

    result = cli_runner.invoke(
        app,
        ["run", str(fixture_video), "--output-dir", str(output_dir), "--auto"],
    )

    assert result.exit_code == 0, result.output
    oss_dir = fake_all["oss_dir"]
    deleted = json.loads((oss_dir / "deleted.json").read_text(encoding="utf-8"))
    assert deleted == ["fake-audio.m4a"]
    assert not (oss_dir / "fake-audio.m4a").exists()


def test_run_passes_prompt_and_count_to_analyze(
    cli_runner: CliRunner, fixture_video: Path, fake_all: dict[str, Path], tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"

    result = cli_runner.invoke(
        app,
        [
            "run",
            str(fixture_video),
            "--output-dir",
            str(output_dir),
            "--prompt",
            "找反转和笑点",
            "--count",
            "5",
        ],
    )

    assert result.exit_code == 0, result.output
    calls = json.loads(
        fake_all["provider_calls_file"].read_text(encoding="utf-8")
    )
    assert len(calls) == 1
    assert calls[0]["count"] == 5
    assert calls[0]["user_prompt"] == "找反转和笑点"


def test_run_default_skips_cut_when_edited_highlights_stay(
    cli_runner: CliRunner, fixture_video: Path, fake_all: dict[str, Path], tmp_path: Path
) -> None:
    """Resume contract: run (stop) -> user edits highlights.json -> run --auto
    must not call the provider again; it cuts the edited list."""
    output_dir = tmp_path / "output"
    target_dir = output_dir / fixture_video.stem

    first = cli_runner.invoke(
        app, ["run", str(fixture_video), "--output-dir", str(output_dir)]
    )
    assert first.exit_code == 0, first.output

    # The user reviews and trims the list down to one highlight.
    write_highlights(output_dir, fixture_video.stem, CANNED_HIGHLIGHTS[:1])

    second = cli_runner.invoke(
        app,
        ["run", str(fixture_video), "--output-dir", str(output_dir), "--auto"],
    )

    assert second.exit_code == 0, second.output
    assert _provider_call_count(fake_all) == 1  # from the first run only
    clips = sorted((target_dir / "clips").glob("*.mp4"))
    assert len(clips) == 1
    assert (target_dir / "merged.mp4").exists()
