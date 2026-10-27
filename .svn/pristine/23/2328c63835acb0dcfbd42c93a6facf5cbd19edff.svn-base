"""Tests that missing cloud config produces actionable errors at the CLI seam."""

from __future__ import annotations

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


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for key in CLOUD_KEYS:
        monkeypatch.delenv(key, raising=False)
    # Isolate from any real .env in the repo root.
    monkeypatch.chdir(tmp_path)


def test_transcribe_with_missing_config_names_missing_keys_and_env_file(
    cli_runner: CliRunner, fixture_video: Path, clean_env: None, tmp_path: Path
) -> None:
    result = cli_runner.invoke(
        app,
        ["transcribe", str(fixture_video), "--output-dir", str(tmp_path / "output")],
    )

    assert result.exit_code != 0
    message = result.output
    for key in CLOUD_KEYS:
        assert key in message
    assert ".env" in message


def test_analyze_with_missing_dashscope_key_names_it(
    cli_runner: CliRunner, fixture_video: Path, clean_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in CLOUD_KEYS[1:]:
        monkeypatch.setenv(key, "dummy")

    result = cli_runner.invoke(
        app,
        ["analyze", str(fixture_video), "--output-dir", str(tmp_path / "output")],
    )

    assert result.exit_code != 0
    message = result.output
    assert "VIDEO_CUT_DASHSCOPE_API_KEY" in message
    assert ".env" in message
