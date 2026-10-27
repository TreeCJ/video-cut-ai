"""Overlap detection for picked highlights (see GLOSSARY: Highlight).

Two picked highlights covering the same scene produce near-duplicate clips —
the live run showed this (a scene picked twice under two titles). Detection
warns; the decision to drop or edit stays with the user.
"""

from __future__ import annotations

from video_cut.cutting import Highlight

# An overlap covering more than this fraction of the shorter highlight is
# reported. Two adjacent clips sharing a second of buffer is normal; a third
# of a clip duplicated is not.
OVERLAP_WARN_RATIO = 0.3


def overlap_seconds(a: Highlight, b: Highlight) -> float:
    """Seconds shared by two highlight windows (0 when disjoint)."""
    return max(0.0, min(a.end, b.end) - max(a.start, b.start))


def find_overlaps(highlights: list[Highlight]) -> list[tuple[Highlight, Highlight, float]]:
    """All (a, b, shared-seconds) pairs whose overlap exceeds the ratio."""
    found: list[tuple[Highlight, Highlight, float]] = []
    for i, a in enumerate(highlights):
        for b in highlights[i + 1 :]:
            shared = overlap_seconds(a, b)
            if shared == 0.0:
                continue
            shorter = min(a.end - a.start, b.end - b.start)
            if shorter > 0 and shared / shorter > OVERLAP_WARN_RATIO:
                found.append((a, b, shared))
    return found
