"""Draft persistence for the web highlight editing view.

Draft is a web-layer concept (see GLOSSARY.md): a working copy of the
Highlight sequence with a per-item ``locked`` flag, stored as
``highlights.draft.json`` next to the immutable ``highlights.json``.
The core ``cutting.Highlight`` contract (five fields) is unchanged;
``locked`` is draft metadata validated here, in the web layer.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from video_cut import paths
from video_cut.cutting import Highlight


@dataclass(frozen=True)
class DraftHighlight:
    """One highlight in the Draft: the five contract fields plus ``locked``."""

    title: str
    reason: str
    quote: str
    start: float
    end: float
    locked: bool

    @property
    def duration(self) -> float:
        return self.end - self.start

    @classmethod
    def from_highlight(cls, highlight: Highlight) -> DraftHighlight:
        """Copy a pipeline Highlight into the draft, unlocked."""
        return cls(
            title=highlight.title,
            reason=highlight.reason,
            quote=highlight.quote,
            start=highlight.start,
            end=highlight.end,
            locked=False,
        )

    @classmethod
    def from_dict(cls, item: Any, context: str) -> DraftHighlight:
        """Validate one draft entry: the five contract fields plus ``locked``."""
        highlight = Highlight.from_dict(item, context)
        locked = item.get("locked", False)
        if not isinstance(locked, bool):
            raise ValueError(f"{context} is invalid: locked must be a bool")
        return cls(
            title=highlight.title,
            reason=highlight.reason,
            quote=highlight.quote,
            start=highlight.start,
            end=highlight.end,
            locked=locked,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_or_create_draft(target_dir: Path) -> list[DraftHighlight]:
    """Read the draft; on first view, copy highlights.json into a new draft.

    The original highlights.json is never written here. Once the draft
    exists it is the only source the editing view reads — a force re-run of
    analyze rewrites highlights.json and resets the draft via
    ``reset_draft_from_highlights`` so the new results are not masked.
    """
    draft_path = target_dir / paths.HIGHLIGHTS_DRAFT_FILE_NAME
    if draft_path.exists():
        raw = json.loads(draft_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(
                f"{draft_path} must contain a JSON list of highlights."
            )
        return [
            DraftHighlight.from_dict(item, f"{draft_path} entry {index + 1}")
            for index, item in enumerate(raw)
        ]

    highlights_path = target_dir / paths.HIGHLIGHTS_FILE_NAME
    raw = json.loads(highlights_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(
            f"{highlights_path} must contain a JSON list of highlights."
        )
    draft = [
        DraftHighlight.from_highlight(
            Highlight.from_dict(item, f"{highlights_path} entry {index + 1}")
        )
        for index, item in enumerate(raw)
    ]
    save_draft(target_dir, draft)
    return draft


def reset_draft_from_highlights(target_dir: Path) -> list[DraftHighlight]:
    """Discard any existing draft and regenerate it from highlights.json.

    Used after a force re-run of analyze: the new highlights.json would be
    masked by the stale draft, so the draft is rebuilt with every item
    unlocked. highlights.json itself is never written here.
    """
    draft_path = target_dir / paths.HIGHLIGHTS_DRAFT_FILE_NAME
    draft_path.unlink(missing_ok=True)
    return load_or_create_draft(target_dir)


def save_draft(target_dir: Path, draft: list[DraftHighlight]) -> None:
    """Rewrite the whole draft file (small JSON; the task lock covers concurrency)."""
    draft_path = target_dir / paths.HIGHLIGHTS_DRAFT_FILE_NAME
    draft_path.write_text(
        json.dumps(
            [highlight.to_dict() for highlight in draft],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
