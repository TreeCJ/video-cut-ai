# 0001: Web UI — manual overrides, draft persistence, and alignment skip

## Status

Accepted (2025)

## Context

The pipeline was CLI-only: `extract-audio → transcribe → analyze → cut`, with
`highlights.json` as the immutable LLM artifact and quote alignment applied
in-memory at cut time. We added a local web UI (FastAPI + HTMX/vanilla JS) for
single-video editing: view per-step artifacts, adjust highlights live, then
cut and merge.

Three decisions had real alternatives and shape the web layer's contract with
the pipeline.

## Decision

### 1. User edits persist to a separate draft file

Edits made in the UI (boundary drags, deletions, reordering) are written to
`highlights.draft.json` in the video's output directory, never to
`highlights.json`. The LLM artifact stays immutable; the draft is the working
copy. When both exist, cut reads the draft.

Alternative considered: keep edits browser-only until the user clicks "cut".
Rejected because a refresh or crash would lose the editing session, and
surviving refresh costs only one small JSON file.

### 2. Manually edited highlights skip quote alignment

A highlight whose start/end the user has dragged is marked **Locked**. At cut
time, locked highlights bypass `align_highlights` and use the user's times
verbatim; unlocked highlights still align via Quote. The UI shows a lock badge.

Alternative considered: re-derive the quote from the transcript over the new
range and let alignment run anyway. Rejected because it breaks the
what-you-see-is-what-you-get contract — the user drags a boundary, previews
it, and would be surprised if cut then moved it again.

### 3. Preview is source-video seek; encoding happens only at final cut

Previewing a highlight (including after adjustments) plays the original video
file from start to end via HTTP range requests — no ffmpeg, zero wait. The
re-encode path (`cut_segment` uniform encoding + stream-copy merge) runs only
when the user confirms the final cut.

Alternative considered: re-encode a clip on every adjustment. Rejected: it
makes interactive dragging impossible (seconds of ffmpeg per drag) for no
fidelity gain, since final boundaries are what get encoded anyway.

## Consequences

- `paths.py` gains the draft filename as the single source of truth.
- The web backend reuses `align_highlights`, `cut_highlights`, and
  `merge_segments` unchanged; locking is handled by filtering which
  highlights go through alignment, not by changing `align.py`.
- The cut command's alignment report (which highlights moved, by how much)
  is surfaced in the UI before encoding starts, mirroring the CLI's warnings.
