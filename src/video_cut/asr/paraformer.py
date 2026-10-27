"""DashScope Paraformer recorded-speech recognition engine.

Submits an async transcription task and polls until completion. API times are
milliseconds; they are converted to seconds for the Transcript contract.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from video_cut.asr import Sentence, Transcript, Word

SUBMIT_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
TASK_URL_TEMPLATE = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

LANGUAGE_HINTS = ["zh", "en"]
MS_PER_SECOND = 1000.0


class TranscriptionFailedError(Exception):
    """Raised when the ASR task ends in a non-SUCCEEDED status."""


class ParaformerEngine:
    """Engine backed by DashScope Paraformer (async task + polling)."""

    def __init__(
        self,
        api_key: str,
        model: str = "paraformer-v2",
        poll_interval_seconds: float = 2.0,
        timeout_seconds: float = 1800.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._poll_interval = poll_interval_seconds
        self._timeout = timeout_seconds
        self._client = client or httpx.Client(timeout=60.0)

    def transcribe(self, audio_url: str) -> Transcript:
        task_id = self._submit(audio_url)
        output = self._poll(task_id)
        # Live API (verified 2026-10): the SUCCEEDED output's results[] carry
        # no inline sentences — only a transcription_url. The real transcript
        # is a second fetch away, shaped as transcripts[] per channel.
        result_url = _find_transcription_url(output)
        payload = self._client.get(result_url)
        payload.raise_for_status()
        return _parse_result(payload.json())

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _submit(self, audio_url: str) -> str:
        response = self._client.post(
            SUBMIT_URL,
            headers={**self._headers(), "X-DashScope-Async": "enable"},
            json={
                "model": self._model,
                "input": {"file_urls": [audio_url]},
                "parameters": {
                    "word_timestamp_enabled": True,
                    "disfluency_removal_enabled": False,
                    "language_hints": LANGUAGE_HINTS,
                },
            },
        )
        response.raise_for_status()
        return response.json()["output"]["task_id"]

    def _poll(self, task_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._timeout
        while True:
            response = self._client.get(
                TASK_URL_TEMPLATE.format(task_id=task_id), headers=self._headers()
            )
            response.raise_for_status()
            output = response.json()["output"]
            status = output["task_status"]
            if status == "SUCCEEDED":
                return output
            if status in ("FAILED", "CANCELED", "UNKNOWN"):
                raise TranscriptionFailedError(
                    f"ASR task {task_id} ended with status {status}: "
                    f"{output.get('message', 'no message')}"
                )
            if time.monotonic() > deadline:
                raise TranscriptionFailedError(
                    f"ASR task {task_id} did not finish within {self._timeout}s"
                )
            time.sleep(self._poll_interval)


def _ms_to_seconds(value_ms: float) -> float:
    return value_ms / MS_PER_SECOND


def _find_transcription_url(output: dict[str, Any]) -> str:
    """Locate the transcription_url in a SUCCEEDED task output.

    The live API nests it: output.results[0].transcription_url (top of each
    result entry). Raise loudly if absent — a silent empty transcript here is
    what produced the blank transcript.json on the first live run.
    """
    for result in output.get("results", []):
        url = result.get("transcription_url")
        if url:
            return url
    raise TranscriptionFailedError(
        f"ASR task {output.get('task_id')} SUCCEEDED but carried no transcription_url"
    )


def _parse_result(payload: dict[str, Any]) -> Transcript:
    """Parse the transcription_url payload into a Transcript (seconds).

    Shape locked to the live API: transcripts[] per channel, each carrying
    sentences[] with begin_time/end_time/text (ms) and words[] whose text
    field is "text" (NOT "word"), plus a "punctuation" field.
    """
    sentences: list[Sentence] = []
    words: list[Word] = []
    for channel in payload.get("transcripts", []):
        for raw_sentence in channel.get("sentences", []):
            sentences.append(
                Sentence(
                    begin_time=_ms_to_seconds(raw_sentence["begin_time"]),
                    end_time=_ms_to_seconds(raw_sentence["end_time"]),
                    text=raw_sentence["text"],
                )
            )
            for raw_word in raw_sentence.get("words", []):
                words.append(
                    Word(
                        begin_time=_ms_to_seconds(raw_word["begin_time"]),
                        end_time=_ms_to_seconds(raw_word["end_time"]),
                        word=raw_word["text"],
                    )
                )
    return Transcript(sentences=tuple(sentences), words=tuple(words))
