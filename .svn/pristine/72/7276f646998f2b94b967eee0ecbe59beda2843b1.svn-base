"""ASR engine abstraction and transcript domain types.

An Engine turns an audio URL into a Transcript (sentences + words with
timestamps in seconds). The default implementation is DashScope Paraformer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Sentence:
    """A span of continuous speech with timestamps in seconds."""

    begin_time: float
    end_time: float
    text: str


@dataclass(frozen=True)
class Word:
    """A single recognized word with timestamps in seconds."""

    begin_time: float
    end_time: float
    word: str


@dataclass(frozen=True)
class Transcript:
    """The complete ASR result for one video: sentences plus words."""

    sentences: tuple[Sentence, ...]
    words: tuple[Word, ...]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "sentences": [
                {"begin_time": s.begin_time, "end_time": s.end_time, "text": s.text}
                for s in self.sentences
            ],
            "words": [
                {"begin_time": w.begin_time, "end_time": w.end_time, "word": w.word}
                for w in self.words
            ],
        }

    @staticmethod
    def from_json_dict(data: dict[str, Any]) -> Transcript:
        return Transcript(
            sentences=tuple(
                Sentence(
                    begin_time=float(s["begin_time"]),
                    end_time=float(s["end_time"]),
                    text=str(s["text"]),
                )
                for s in data["sentences"]
            ),
            words=tuple(
                Word(
                    begin_time=float(w["begin_time"]),
                    end_time=float(w["end_time"]),
                    word=str(w["word"]),
                )
                for w in data["words"]
            ),
        )


class Engine(Protocol):
    """ASR engine: audio URL in, Transcript out."""

    def transcribe(self, audio_url: str) -> Transcript:
        """Transcribe the audio at the given URL."""
        ...


def write_transcript(transcript: Transcript, path: Path) -> None:
    """Write a Transcript to disk as transcript.json."""
    path.write_text(
        json.dumps(transcript.to_json_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_transcript(path: Path) -> Transcript:
    """Read a transcript.json back into a Transcript."""
    return Transcript.from_json_dict(json.loads(path.read_text(encoding="utf-8")))
