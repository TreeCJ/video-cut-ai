"""Quote-anchor timestamp alignment.

Each Highlight carries a ``quote``: the Transcript sentence the LLM picked
the segment for. That quote is the verification anchor — the LLM's own
``start``/``end`` are treated as hints and corrected against the sentence
positions, which are the single source of truth for timing (see GLOSSARY:
Quote).

Alignment runs in-flight inside the cut flow; highlights.json on disk is
never modified.

The rule set is deliberately small — three rules:

1. **Anchor the start to the quote.** The quote is fuzzy-matched against
   every Transcript Sentence. On a match (score >= QUOTE_MATCH_THRESHOLD),
   the clip starts at ``sentence.begin_time - head`` where ``head`` is
   BUFFER_S shrunk to half the gap from the previous sentence (clamped at
   0 — the clamp matters for a sentence at the very start of the video).
   Back-to-back speech gets no buffer, so the clip never swallows the
   previous sentence's trailing words.
   If the LLM ``start`` deviates from the matched position by more than
   DEVIATION_TOLERANCE_S, a warning is emitted; the transcript position
   wins either way.
2. **Keep the end.** The quote only anchors where the segment begins; a
   Highlight may span several sentences. The clip ends at
   ``max(llm_end, sentence.end_time) + tail`` — never shorter than the
   anchored sentence, longer when the LLM intended a multi-sentence span.
   ``tail`` follows the same adaptive rule as ``head`` against the next
   sentence.
3. **No match.** When no sentence clears the threshold, the best-scoring
   candidate is used as a position hint: if it sits within
   DEVIATION_TOLERANCE_S of the LLM start, the transcript position still
   wins (with a warning); otherwise the quote is treated as foreign — a
   warning is emitted and the raw LLM timestamps are used unchanged.

All returned timestamps are additionally clamped at 0, so a buffered start
never goes negative.
"""

from __future__ import annotations

import warnings
from dataclasses import replace

from rapidfuzz import fuzz, process

from video_cut.asr import Transcript
from video_cut.cutting import Highlight

# Fuzzy-match score (0-100) a quote must reach against a sentence to count
# as anchored. 80 accepts light ASR paraphrase; below it the "match" is
# coincidence and rule 3 applies.
QUOTE_MATCH_THRESHOLD = 80.0

# Buffer added on each side of an aligned boundary (seconds).
BUFFER_S = 0.5

# Deviation between the LLM start and the anchored sentence start beyond
# which a loud warning is emitted (seconds).
DEVIATION_TOLERANCE_S = 3.0


def _buffered_bounds(
    sentences: tuple, index: int, llm_end: float
) -> tuple[float, float]:
    """Clip bounds around the anchored sentence, with adaptive buffering.

    The nominal BUFFER_S padding applies only when the gap to the neighbour
    sentence allows it: back-to-back speech (gap near zero, the common case
    in dense narration) gets no buffer, so the clip never swallows the
    neighbour's opening or trailing words. The buffer never exceeds half
    the gap on either side.

    ``llm_end`` may extend past the anchored sentence when the highlight
    spans several sentences; the end is max(llm_end, sentence end) before
    buffering.
    """
    sentence = sentences[index]
    prev_end = sentences[index - 1].end_time if index > 0 else None

    head = BUFFER_S if prev_end is None else min(BUFFER_S, (sentence.begin_time - prev_end) / 2)
    end_base = max(llm_end, sentence.end_time)
    # The end may land inside a later sentence (multi-sentence span); the
    # tail buffer must respect that sentence's successor, not the anchor's.
    next_begin = next(
        (s.begin_time for s in sentences[index + 1 :] if s.begin_time >= end_base),
        None,
    )
    tail = BUFFER_S if next_begin is None else min(BUFFER_S, (next_begin - end_base) / 2)

    start = max(0.0, sentence.begin_time - max(0.0, head))
    end = end_base + max(0.0, tail)
    return start, end


def align_highlights(
    highlights: list[Highlight], transcript: Transcript
) -> list[Highlight]:
    """Align each highlight's timestamps to the transcript via its quote.

    Returns new Highlight objects (input untouched); emits one warning per
    correction or unmatched quote.
    """
    return [align_highlight(h, transcript) for h in highlights]


def align_highlight(highlight: Highlight, transcript: Transcript) -> Highlight:
    """Align one highlight against the transcript sentences."""
    if not transcript.sentences:
        warnings.warn(
            f"Highlight {highlight.title!r}: transcript has no sentences; "
            f"keeping LLM timestamps {highlight.start:.2f}-{highlight.end:.2f}s.",
            stacklevel=2,
        )
        return highlight

    match = process.extractOne(
        highlight.quote,
        [sentence.text for sentence in transcript.sentences],
        scorer=fuzz.ratio,
        score_cutoff=QUOTE_MATCH_THRESHOLD,
    )
    if match is None:
        # No sentence clears the threshold. Fall back to the best-scoring
        # candidate (if any) purely as a position hint: when it sits within
        # DEVIATION_TOLERANCE_S of the LLM start, the transcript position is
        # still the better anchor; otherwise the quote is genuinely foreign
        # and the raw LLM timestamps are kept.
        best = process.extractOne(
            highlight.quote,
            [sentence.text for sentence in transcript.sentences],
            scorer=fuzz.ratio,
        )
        candidate = transcript.sentences[best[2]] if best is not None else None
        if (
            candidate is not None
            and abs(highlight.start - candidate.begin_time) <= DEVIATION_TOLERANCE_S
        ):
            warnings.warn(
                f"Highlight {highlight.title!r}: quote did not match any "
                f"transcript sentence, but the best candidate "
                f"({candidate.begin_time:.2f}s) is within "
                f"{DEVIATION_TOLERANCE_S:.0f}s of the LLM start "
                f"{highlight.start:.2f}s; using the transcript position.",
                stacklevel=2,
            )
            start, end = _buffered_bounds(
                transcript.sentences, best[2], highlight.end
            )
            return replace(highlight, start=start, end=end)
        warnings.warn(
            f"Highlight {highlight.title!r}: quote did not match any transcript "
            f"sentence; keeping LLM timestamps "
            f"{highlight.start:.2f}-{highlight.end:.2f}s.",
            stacklevel=2,
        )
        return highlight

    _, _, index = match
    sentence = transcript.sentences[index]

    if abs(highlight.start - sentence.begin_time) > DEVIATION_TOLERANCE_S:
        warnings.warn(
            f"Highlight {highlight.title!r}: LLM start {highlight.start:.2f}s "
            f"deviates from quote's actual position {sentence.begin_time:.2f}s "
            f"by more than {DEVIATION_TOLERANCE_S:.0f}s; using the transcript "
            f"position.",
            stacklevel=2,
        )

    start, end = _buffered_bounds(transcript.sentences, index, highlight.end)
    return replace(highlight, start=start, end=end)
