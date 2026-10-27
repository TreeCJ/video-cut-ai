"""Overlap detection rules (pure) and the analyze command's overlap warning."""

from __future__ import annotations

from video_cut.cutting import Highlight
from video_cut.overlap import OVERLAP_WARN_RATIO, find_overlaps, overlap_seconds


def _h(start: float, end: float, title: str = "t") -> Highlight:
    return Highlight(title=title, reason="r", quote="q", start=start, end=end)


def test_disjoint_highlights_do_not_overlap() -> None:
    assert overlap_seconds(_h(0, 10), _h(20, 30)) == 0.0


def test_touching_highlights_do_not_overlap() -> None:
    assert overlap_seconds(_h(0, 10), _h(10, 20)) == 0.0


def test_overlap_seconds_measures_shared_window() -> None:
    assert overlap_seconds(_h(0, 15), _h(10, 30)) == 5.0


def test_find_overlaps_flags_pair_above_ratio() -> None:
    # Live-run case: 2213.9-2240.5 vs 2206.5-2236.9 share 23s of ~27s.
    highlights = [_h(2213.9, 2240.5, "a"), _h(2206.5, 2236.9, "b")]
    overlaps = find_overlaps(highlights)
    assert len(overlaps) == 1
    assert overlaps[0][2] == 2236.9 - 2213.9


def test_find_overlaps_ignores_small_shared_buffer() -> None:
    # Two clips sharing 1s of buffer on 30s clips is adjacency, not duplication.
    highlights = [_h(0, 30), _h(29.5, 60)]
    assert find_overlaps(highlights) == []


def test_overlap_ratio_threshold_documented() -> None:
    assert 0 < OVERLAP_WARN_RATIO < 1
