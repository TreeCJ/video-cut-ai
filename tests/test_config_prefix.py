"""Prefix isolation: unprefixed process env vars must not leak into config."""

from __future__ import annotations

import pytest

from video_cut.config import ASR_CONFIG_KEYS, MissingConfigError, require_config

LEGACY_KEYS = (
    "DASHSCOPE_API_KEY",
    "OSS_BUCKET",
    "OSS_ENDPOINT",
    "OSS_ACCESS_KEY_ID",
    "OSS_ACCESS_KEY_SECRET",
)


@pytest.fixture()
def no_dotenv(monkeypatch, tmp_path):
    """Run config loading away from any real .env (cwd-relative loading)."""
    monkeypatch.chdir(tmp_path)
    for key in ASR_CONFIG_KEYS:
        monkeypatch.delenv(key, raising=False)
    return tmp_path


def test_unprefixed_process_env_does_not_satisfy_required_keys(no_dotenv, monkeypatch) -> None:
    """Legacy exports like OSS_ACCESS_KEY_ID (from other projects) are ignored."""
    for key in LEGACY_KEYS:
        monkeypatch.setenv(key, f"legacy-{key}")

    with pytest.raises(MissingConfigError):
        require_config(ASR_CONFIG_KEYS)


def test_prefixed_process_env_overrides_dotenv(no_dotenv, monkeypatch) -> None:
    """VIDEO_CUT_* in the process env wins over .env (documented precedence)."""
    (no_dotenv / ".env").write_text(
        "VIDEO_CUT_DASHSCOPE_API_KEY=dotenv-key\n", encoding="utf-8"
    )
    monkeypatch.setenv("VIDEO_CUT_DASHSCOPE_API_KEY", "process-key")

    env = require_config(ASR_CONFIG_KEYS[:1])
    assert env["VIDEO_CUT_DASHSCOPE_API_KEY"] == "process-key"


def test_dotenv_prefixed_values_are_read(no_dotenv) -> None:
    (no_dotenv / ".env").write_text(
        "VIDEO_CUT_DASHSCOPE_API_KEY=dotenv-key\nOSS_ACCESS_KEY_ID=legacy\n",
        encoding="utf-8",
    )

    env = require_config(ASR_CONFIG_KEYS[:1])
    assert env["VIDEO_CUT_DASHSCOPE_API_KEY"] == "dotenv-key"
