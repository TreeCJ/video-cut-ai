"""Unit tests for the Paraformer engine's ms→s conversion and task polling.

The HTTP layer is replaced by an httpx MockTransport; no network access.
"""

from __future__ import annotations

import json

import httpx
import pytest

from video_cut.asr.paraformer import (
    SUBMIT_URL,
    ParaformerEngine,
    TranscriptionFailedError,
)

# Canned responses, shape locked to the REAL DashScope Paraformer API as
# captured on a live run (2026-10): the task output's results[] carry only a
# transcription_url; the actual transcript lives behind that URL as
# transcripts[] per channel, each with sentences[] whose words use "text"
# (not "word"). Times in milliseconds.
TASK_ID = "task-abc123"
RESULT_URL = "https://example.invalid/result.json"
SUCCEEDED_OUTPUT = {
    "task_id": TASK_ID,
    "task_status": "SUCCEEDED",
    "results": [
        {
            "file_url": "https://oss.local/audio.m4a",
            "subtask_status": "SUCCEEDED",
            "transcription_url": RESULT_URL,
            "results": [],
        }
    ],
}
TRANSCRIPTION_PAYLOAD = {
    "file_url": "https://oss.local/audio.m4a",
    "properties": {"audio_format": "aac", "original_duration_in_milliseconds": 6000},
    "transcripts": [
        {
            "channel_id": 0,
            "content_duration_in_milliseconds": 5000,
            "text": "大家好。 hello world",
            "sentences": [
                {
                    "begin_time": 500,
                    "end_time": 2000,
                    "text": "大家好。",
                    "sentence_id": 1,
                    "words": [
                        {"begin_time": 500, "end_time": 800, "text": "大家", "punctuation": ""},
                        {"begin_time": 800, "end_time": 1000, "text": "好", "punctuation": "。"},
                    ],
                },
                {
                    "begin_time": 2500,
                    "end_time": 5000,
                    "text": "hello world",
                    "sentence_id": 2,
                    "words": [
                        {"begin_time": 2500, "end_time": 2900, "text": "hello", "punctuation": ""},
                        {"begin_time": 2900, "end_time": 3200, "text": "world", "punctuation": ""},
                    ],
                },
            ],
        }
    ],
}


def _make_engine(handler) -> ParaformerEngine:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ParaformerEngine(
        api_key="test-key",
        poll_interval_seconds=0,
        client=client,
    )


def test_transcribe_converts_milliseconds_to_seconds() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/transcription"):
            return httpx.Response(200, json={"output": {"task_id": TASK_ID}})
        if request.url.host == "example.invalid":
            return httpx.Response(200, json=TRANSCRIPTION_PAYLOAD)
        return httpx.Response(200, json={"output": SUCCEEDED_OUTPUT})

    transcript = _make_engine(handler).transcribe("https://oss.local/audio.m4a")

    assert [s.begin_time for s in transcript.sentences] == [0.5, 2.5]
    assert [s.end_time for s in transcript.sentences] == [2.0, 5.0]
    assert transcript.sentences[0].text == "大家好。"
    assert [(w.begin_time, w.end_time, w.word) for w in transcript.words] == [
        (0.5, 0.8, "大家"),
        (0.8, 1.0, "好"),
        (2.5, 2.9, "hello"),
        (2.9, 3.2, "world"),
    ]


def test_submit_enables_word_timestamps_and_keeps_disfluencies() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/transcription"):
            captured["body"] = json.loads(request.content)
            captured["async_header"] = request.headers.get("X-DashScope-Async")
            captured["auth"] = request.headers.get("Authorization")
            return httpx.Response(200, json={"output": {"task_id": TASK_ID}})
        if request.url.host == "example.invalid":
            return httpx.Response(200, json=TRANSCRIPTION_PAYLOAD)
        return httpx.Response(200, json={"output": SUCCEEDED_OUTPUT})

    _make_engine(handler).transcribe("https://oss.local/audio.m4a")

    body = captured["body"]
    assert body["parameters"]["word_timestamp_enabled"] is True
    assert body["parameters"]["disfluency_removal_enabled"] is False
    assert body["input"]["file_urls"] == ["https://oss.local/audio.m4a"]
    assert captured["async_header"] == "enable"
    assert captured["auth"] == "Bearer test-key"


def test_poll_until_succeeded() -> None:
    polls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/transcription"):
            return httpx.Response(200, json={"output": {"task_id": TASK_ID}})
        if request.url.host == "example.invalid":
            return httpx.Response(200, json=TRANSCRIPTION_PAYLOAD)
        polls["count"] += 1
        if polls["count"] < 3:
            return httpx.Response(
                200, json={"output": {"task_id": TASK_ID, "task_status": "RUNNING"}}
            )
        return httpx.Response(200, json={"output": SUCCEEDED_OUTPUT})

    transcript = _make_engine(handler).transcribe("https://oss.local/audio.m4a")

    assert polls["count"] == 3
    assert len(transcript.sentences) == 2


def test_failed_task_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/transcription"):
            return httpx.Response(200, json={"output": {"task_id": TASK_ID}})
        return httpx.Response(
            200,
            json={
                "output": {
                    "task_id": TASK_ID,
                    "task_status": "FAILED",
                    "message": "audio download failed",
                }
            },
        )

    with pytest.raises(TranscriptionFailedError, match="FAILED"):
        _make_engine(handler).transcribe("https://oss.local/audio.m4a")
