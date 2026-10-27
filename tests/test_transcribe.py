"""Tests for the transcribe command at the CLI seam.

External services are replaced by fakes injected via env config:
- VIDEO_CUT_ASR_ENGINE_FAKE: canned engine payload (shape locked to Transcript)
- VIDEO_CUT_OSS_FAKE_DIR: local-directory stand-in for OSS that records deletes

No test touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
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
        {"begin_time": 2.5, "end_time": 5.0, "text": "今天聊一个反常识的结论。"},
    ],
    "words": [
        {"begin_time": 0.5, "end_time": 0.8, "word": "大家"},
        {"begin_time": 0.8, "end_time": 1.0, "word": "好"},
        {"begin_time": 2.5, "end_time": 2.8, "word": "今天"},
    ],
}


@pytest.fixture()
def fake_services(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, Path]:
    """Scrub real cloud config, then inject fake engine + fake OSS."""
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
    monkeypatch.setenv("VIDEO_CUT_OSS_FAKE_DIR", str(oss_dir))
    monkeypatch.setenv("_VIDEO_CUT_FAKE_ENGINE_URLS_FILE", str(engine_urls_file))
    monkeypatch.setenv("VIDEO_CUT_ASR_ENGINE_FAKE", json.dumps(ENGINE_PAYLOAD))

    return {"oss_dir": oss_dir, "engine_urls_file": engine_urls_file}


def _stage_audio(output_dir: Path, video: Path) -> Path:
    """Stage a pre-existing audio.m4a as if extract-audio already ran."""
    target_dir = output_dir / video.stem
    target_dir.mkdir(parents=True, exist_ok=True)
    audio = target_dir / "audio.m4a"
    audio.write_bytes(b"fake audio bytes")
    return audio


def test_transcribe_writes_transcript_json_with_sentence_and_word_timestamps(
    cli_runner: CliRunner, fixture_video: Path, fake_services: dict[str, Path], tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _stage_audio(output_dir, fixture_video)

    result = cli_runner.invoke(
        app, ["transcribe", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code == 0, result.output
    transcript_path = output_dir / fixture_video.stem / "transcript.json"
    assert transcript_path.exists()

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert transcript["sentences"] == ENGINE_PAYLOAD["sentences"]
    assert transcript["words"] == ENGINE_PAYLOAD["words"]
    # Times are seconds (per the glossary), not the API's milliseconds.
    for sentence in transcript["sentences"]:
        assert sentence["begin_time"] < 100
    for word in transcript["words"]:
        assert word["begin_time"] < 100


def test_transcribe_deletes_oss_object_on_success(
    cli_runner: CliRunner, fixture_video: Path, fake_services: dict[str, Path], tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _stage_audio(output_dir, fixture_video)

    result = cli_runner.invoke(
        app, ["transcribe", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code == 0, result.output
    oss_dir = fake_services["oss_dir"]
    deleted = json.loads((oss_dir / "deleted.json").read_text(encoding="utf-8"))
    assert deleted == ["fake-audio.m4a"]
    # The staged object itself is gone, not just recorded as deleted.
    assert not (oss_dir / "fake-audio.m4a").exists()


def test_transcribe_deletes_oss_object_on_engine_failure(
    cli_runner: CliRunner,
    fixture_video: Path,
    fake_services: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "output"
    _stage_audio(output_dir, fixture_video)
    monkeypatch.setenv(
        "VIDEO_CUT_ASR_ENGINE_FAKE",
        json.dumps({"error": "ASR task FAILED: upstream exploded", "sentences": [], "words": []}),
    )

    result = cli_runner.invoke(
        app, ["transcribe", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code != 0
    assert not (output_dir / fixture_video.stem / "transcript.json").exists()
    deleted = json.loads(
        (fake_services["oss_dir"] / "deleted.json").read_text(encoding="utf-8")
    )
    assert deleted == ["fake-audio.m4a"]


def test_transcribe_skips_when_transcript_exists(
    cli_runner: CliRunner, fixture_video: Path, fake_services: dict[str, Path], tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _stage_audio(output_dir, fixture_video)
    transcript_path = output_dir / fixture_video.stem / "transcript.json"
    transcript_path.write_text('{"sentences": [], "words": []}', encoding="utf-8")

    result = cli_runner.invoke(
        app, ["transcribe", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code == 0, result.output
    assert "Skipping" in result.output
    # The engine was never called: no upload, no signed URL handed out.
    assert not fake_services["engine_urls_file"].exists()
    assert not (fake_services["oss_dir"] / "deleted.json").exists()


def test_transcribe_force_reruns_when_transcript_exists(
    cli_runner: CliRunner, fixture_video: Path, fake_services: dict[str, Path], tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _stage_audio(output_dir, fixture_video)
    transcript_path = output_dir / fixture_video.stem / "transcript.json"
    transcript_path.write_text('{"sentences": [], "words": []}', encoding="utf-8")

    result = cli_runner.invoke(
        app,
        ["transcribe", str(fixture_video), "--output-dir", str(output_dir), "--force"],
    )

    assert result.exit_code == 0, result.output
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert transcript["sentences"] == ENGINE_PAYLOAD["sentences"]


def test_transcribe_fails_when_audio_missing(
    cli_runner: CliRunner, fixture_video: Path, fake_services: dict[str, Path], tmp_path: Path
) -> None:
    result = cli_runner.invoke(
        app, ["transcribe", str(fixture_video), "--output-dir", str(tmp_path / "output")]
    )

    assert result.exit_code != 0
    assert "extract-audio" in result.output
