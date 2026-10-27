"""Configuration loading from .env / environment variables.

All keys are VIDEO_CUT_-prefixed so unrelated process-env exports (a global
OSS_ACCESS_KEY_ID for another project, say) can never leak into this tool's
config. Only prefixed keys are read; a prefixed process-env value still wins
over .env, which is the documented override channel for CI and one-off runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from dotenv import dotenv_values

ENV_FILE_NAME = ".env"
ENV_EXAMPLE_FILE_NAME = ".env.example"

ASR_CONFIG_KEYS = (
    "VIDEO_CUT_DASHSCOPE_API_KEY",
)

# 向后兼容：旧的代码可能引用 ASR_CONFIG_KEYS_REQUIRED
ASR_CONFIG_KEYS_REQUIRED = ASR_CONFIG_KEYS

LLM_CONFIG_KEYS = ("VIDEO_CUT_DASHSCOPE_API_KEY",)

ASR_MODEL_KEY = "VIDEO_CUT_ASR_MODEL"
LLM_MODEL_KEY = "VIDEO_CUT_LLM_MODEL"

DEFAULT_ASR_MODEL = "paraformer-realtime-v2"
DEFAULT_LLM_MODEL = "qwen-plus"


@dataclass(frozen=True)
class MissingConfigError(Exception):
    """Raised when required configuration keys are absent."""

    missing_keys: tuple[str, ...]

    def __str__(self) -> str:
        keys = ", ".join(self.missing_keys)
        return (
            f"Missing required configuration: {keys}. "
            f"Copy {ENV_EXAMPLE_FILE_NAME} to {ENV_FILE_NAME} "
            f"and fill in the values."
        )


def _load_env() -> dict[str, str]:
    """Merge VIDEO_CUT_-prefixed .env values with prefixed process env (env wins).

    Unprefixed variables in either source are invisible to this tool.
    """
    import os

    values = {
        k: v
        for k, v in dotenv_values(ENV_FILE_NAME).items()
        if v and k.startswith("VIDEO_CUT_")
    }
    process = {
        k: v
        for k, v in os.environ.items()
        if v and k.startswith("VIDEO_CUT_")
    }
    return {**values, **process}


def require_config(required_keys: tuple[str, ...]) -> dict[str, str]:
    """Return the configured values for required keys, or raise MissingConfigError."""
    env = _load_env()
    missing = tuple(key for key in required_keys if key not in env)
    if missing:
        raise MissingConfigError(missing_keys=missing)
    return {key: env[key] for key in required_keys}
