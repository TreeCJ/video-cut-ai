"""Tests for configuration loading and the .env contract."""

from __future__ import annotations

from pathlib import Path

REQUIRED_CONFIG_KEYS = [
    "VIDEO_CUT_DASHSCOPE_API_KEY",
    "VIDEO_CUT_OSS_BUCKET",
    "VIDEO_CUT_OSS_ENDPOINT",
    "VIDEO_CUT_OSS_ACCESS_KEY_ID",
    "VIDEO_CUT_OSS_ACCESS_KEY_SECRET",
]

MODEL_CONFIG_KEYS = ["VIDEO_CUT_ASR_MODEL", "VIDEO_CUT_LLM_MODEL"]


def test_env_example_lists_all_config_keys() -> None:
    env_example = (
        Path(__file__).parent.parent / ".env.example"
    ).read_text(encoding="utf-8")

    for key in [*REQUIRED_CONFIG_KEYS, *MODEL_CONFIG_KEYS]:
        assert key in env_example, f".env.example is missing {key}"


def test_env_example_model_keys_have_defaults() -> None:
    """Model names ship with overridable defaults, per the spec."""
    env_example = (
        Path(__file__).parent.parent / ".env.example"
    ).read_text(encoding="utf-8")

    assert "VIDEO_CUT_ASR_MODEL=paraformer-v2" in env_example
    assert "VIDEO_CUT_LLM_MODEL=" in env_example
