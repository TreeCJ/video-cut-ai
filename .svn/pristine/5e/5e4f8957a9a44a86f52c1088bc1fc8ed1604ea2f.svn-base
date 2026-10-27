"""LLM Provider abstraction for highlight picking (see GLOSSARY: Provider).

A Provider reads a Transcript and returns Highlight candidates. The default
implementation is QwenProvider (DashScope 通义千问, OpenAI-compatible
endpoint with JSON structured output). The HTTP client is injectable so
tests can exercise the provider without network access.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from video_cut.asr import Transcript
from video_cut.cutting import Highlight
from video_cut.llm.prompt import build_system_prompt, build_user_prompt

DASHSCOPE_CHAT_COMPLETIONS_URL = (
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
)

DEFAULT_TIMEOUT_S = 120.0


class HighlightAnalysisError(Exception):
    """The LLM reply could not be turned into valid Highlight objects."""


class Provider(Protocol):
    """LLM provider: Transcript plus user direction in, Highlights out."""

    def pick_highlights(
        self,
        transcript: Transcript,
        user_prompt: str,
        count: int,
        max_duration: float,
    ) -> list[Highlight]:
        """Pick up to ``count`` highlights within ``max_duration`` total seconds."""
        ...


class QwenProvider:
    """DashScope 通义千问 via the OpenAI-compatible chat completions API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client

    def pick_highlights(
        self,
        transcript: Transcript,
        user_prompt: str,
        count: int,
        max_duration: float,
    ) -> list[Highlight]:
        raw_text = self._complete(transcript, user_prompt, count, max_duration)
        return parse_highlights(raw_text)

    def _complete(
        self,
        transcript: Transcript,
        user_prompt: str,
        count: int,
        max_duration: float,
    ) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": build_system_prompt()},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        transcript, user_prompt, count, max_duration
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._client is not None:
            response = self._client.post(
                DASHSCOPE_CHAT_COMPLETIONS_URL, json=payload, headers=headers
            )
        else:
            with httpx.Client(timeout=DEFAULT_TIMEOUT_S) as client:
                response = client.post(
                    DASHSCOPE_CHAT_COMPLETIONS_URL, json=payload, headers=headers
                )
        response.raise_for_status()
        body = response.json()
        try:
            return str(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as error:
            raise HighlightAnalysisError(
                f"Unexpected LLM API response shape: {error}"
            ) from error


def parse_highlights(raw_text: str) -> list[Highlight]:
    """Parse the LLM's raw reply into Highlights, validating the contract.

    Raises HighlightAnalysisError when the reply is not valid JSON, is not a
    list of objects, or any item fails the contract (five fields present,
    start/end numeric with start < end). Nothing is partially returned —
    a malformed reply fails the whole analysis rather than silently
    dropping items.
    """
    try:
        data: Any = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise HighlightAnalysisError(
            f"LLM output is not valid JSON: {error}"
        ) from error

    # The model may wrap the array in an object despite the prompt contract.
    if isinstance(data, dict):
        list_values = [value for value in data.values() if isinstance(value, list)]
        if len(list_values) == 1:
            data = list_values[0]
    if not isinstance(data, list):
        raise HighlightAnalysisError(
            "LLM output must be a JSON array of highlight objects."
        )

    highlights = []
    for index, item in enumerate(data):
        try:
            highlight = Highlight.from_dict(item, f"LLM output entry {index + 1}")
        except ValueError as error:
            raise HighlightAnalysisError(str(error)) from error
        highlights.append(highlight)
    return highlights


def write_highlights(highlights: list[Highlight], path: Path) -> None:
    """Write highlights.json in the exact contract shape."""
    payload = [
        {
            "title": h.title,
            "reason": h.reason,
            "quote": h.quote,
            "start": h.start,
            "end": h.end,
        }
        for h in highlights
    ]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
