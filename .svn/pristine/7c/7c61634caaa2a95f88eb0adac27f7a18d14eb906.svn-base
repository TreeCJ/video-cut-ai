"""Unit tests for the three alignment rules on one highlight.

The CLI-seam behaviour is covered in tests/test_align.py; here the rule set
itself is exercised directly, including the below-threshold middle branch:
quote unmatched but best candidate within 3s of the LLM start -> align to
the transcript position (with warning); no candidate near -> keep LLM times.
"""

from __future__ import annotations

import pytest

from video_cut.align import BUFFER_S, align_highlight
from video_cut.asr import Sentence, Transcript
from video_cut.cutting import Highlight


def _sentence(begin: float, end: float, text: str) -> Sentence:
    return Sentence(begin_time=begin, end_time=end, text=text)


def _highlight(start: float, end: float, quote: str = "zzz no match qqq") -> Highlight:
    return Highlight(title="t", reason="r", quote=quote, start=start, end=end)


def test_below_threshold_quote_with_candidate_near_llm_start_uses_transcript() -> None:
    """Quote matches nothing, but the best-scoring sentence sits within 3s of
    the LLM start -> warn and align to that sentence's position."""
    transcript = Transcript(sentences=(_sentence(5.0, 7.0, "完全不同的句子内容"),), words=())
    highlight = _highlight(start=6.0, end=9.0)

    with pytest.warns(UserWarning, match="best candidate"):
        aligned = align_highlight(highlight, transcript)

    assert aligned.start == 5.0 - BUFFER_S
    assert aligned.end == 9.0 + BUFFER_S


def test_below_threshold_quote_with_no_candidate_near_llm_start_keeps_llm() -> None:
    """Best candidate deviates from the LLM start by > 3s -> warn and keep the
    raw LLM timestamps unchanged."""
    transcript = Transcript(sentences=(_sentence(5.0, 7.0, "完全不同的句子内容"),), words=())
    highlight = _highlight(start=20.0, end=25.0)

    with pytest.warns(UserWarning, match="keeping LLM timestamps"):
        aligned = align_highlight(highlight, transcript)

    assert aligned.start == 20.0
    assert aligned.end == 25.0
