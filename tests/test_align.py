"""Tests for quote-anchor timestamp alignment at the `cut` CLI seam.

Alignment runs in-flight inside the cut flow: the quote of each Highlight is
fuzzy-matched against the Transcript's Sentences, and the produced clip
boundaries follow the matched sentence position (with buffers) rather than
the raw LLM timestamps. highlights.json on disk is never modified.

ffmpeg is real in these tests: the fixture video is generated programmatically
(10s color bars + sine tone) and assertions use ffprobe on produced artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from tests.conftest import ffprobe_duration, write_highlights
from video_cut.cli import app

# One frame at the CFR 30fps segment rate.
FRAME_TOLERANCE_S = 1.0 / 30.0

# The transcript the fixture video "spoke": three sentences with known
# boundaries. Quote matching anchors against these positions.
TRANSCRIPT = {
    "sentences": [
        {"begin_time": 1.0, "end_time": 3.0, "text": "今天我们讲一个反常识的结论"},
        {"begin_time": 4.0, "end_time": 6.0, "text": "其实百分之九十的人都搞错了"},
        {"begin_time": 7.0, "end_time": 9.0, "text": "最后我们总结一下今天的内容"},
    ],
    "words": [],
}


def _write_transcript(output_dir: Path, video_stem: str) -> Path:
    target_dir = output_dir / video_stem
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "transcript.json"
    path.write_text(json.dumps(TRANSCRIPT, ensure_ascii=False), encoding="utf-8")
    return path


def _run_cut(cli_runner: CliRunner, video: Path, output_dir: Path, *extra: str):
    return cli_runner.invoke(
        app, ["cut", str(video), "--output-dir", str(output_dir), *extra]
    )


def _single_clip(output_dir: Path, video_stem: str) -> Path:
    clips = sorted((output_dir / video_stem / "clips").glob("*.mp4"))
    assert len(clips) == 1
    return clips[0]


def test_aligned_clip_boundaries_follow_sentence_plus_buffer(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    """Quote matches sentence 2 (4.0-6.0s) and LLM timestamps are close.

    The clip must span the sentence boundaries with a 0.5s buffer on each
    side: 3.5s to 6.5s, i.e. duration == sentence span + 1.0s.
    """
    output_dir = tmp_path / "output"
    _write_transcript(output_dir, fixture_video.stem)
    write_highlights(
        output_dir,
        fixture_video.stem,
        [
            {
                "title": "hook",
                "reason": "close to the real position",
                "quote": "其实百分之九十的人都搞错了",
                "start": 4.2,
                "end": 5.8,
            }
        ],
    )

    result = _run_cut(cli_runner, fixture_video, output_dir)

    assert result.exit_code == 0, result.output
    clip = _single_clip(output_dir, fixture_video.stem)
    duration = ffprobe_duration(clip)
    assert abs(duration - 3.0) <= FRAME_TOLERANCE_S


def test_deviant_llm_timestamps_are_corrected_with_warning(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    """LLM start deviates from the matched sentence by > 3s.

    The transcript position wins for the anchor: the clip starts at
    sentence.begin - 0.5 and a warning is printed.
    """
    output_dir = tmp_path / "output"
    _write_transcript(output_dir, fixture_video.stem)
    write_highlights(
        output_dir,
        fixture_video.stem,
        [
            {
                "title": "deviant",
                "reason": "LLM hallucinated the position",
                "quote": "其实百分之九十的人都搞错了",
                # Real position is 4.0-6.0s; start is 5.8s early.
                "start": 9.8,
                "end": 9.9,
            }
        ],
    )

    result = _run_cut(cli_runner, fixture_video, output_dir)

    assert result.exit_code == 0, result.output
    assert "warning" in result.output.lower()
    clip = _single_clip(output_dir, fixture_video.stem)
    # Corrected: start = 4.0 - 0.5 = 3.5. The LLM end (9.9s) exceeds the
    # sentence end (6.0s), so it is kept with buffer: end = 9.9 + 0.5.
    # Duration = 10.4 - 3.5 = 6.9s... but the source video is only 10s long,
    # so ffmpeg clamps at EOF: duration = 10.0 - 3.5 = 6.5s.
    duration = ffprobe_duration(clip)
    assert abs(duration - 6.5) <= FRAME_TOLERANCE_S


def test_unmatched_quote_keeps_llm_timestamps_with_warning(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    """A quote that matches no sentence AND whose LLM start is > 3s from the
    best candidate falls back to raw LLM timestamps (spec: 匹配不到且无候选)."""
    output_dir = tmp_path / "output"
    _write_transcript(output_dir, fixture_video.stem)
    write_highlights(
        output_dir,
        fixture_video.stem,
        [
            {
                "title": "unmatched",
                "reason": "quote not in transcript",
                "quote": "这句话在转录里完全不存在xyz",
                # Best candidate sits at 1.0s; this start is far from every
                # sentence, so no transcript position is trustworthy here.
                "start": 5.0,
                "end": 7.0,
            }
        ],
    )

    result = _run_cut(cli_runner, fixture_video, output_dir)

    assert result.exit_code == 0, result.output
    assert "warning" in result.output.lower()
    clip = _single_clip(output_dir, fixture_video.stem)
    duration = ffprobe_duration(clip)
    assert abs(duration - 2.0) <= FRAME_TOLERANCE_S


def test_cut_without_transcript_uses_raw_timestamps_with_warning(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    """No transcript.json on disk: cut still works standalone on raw times."""
    output_dir = tmp_path / "output"
    write_highlights(
        output_dir,
        fixture_video.stem,
        [
            {
                "title": "standalone",
                "reason": "no transcript available",
                "quote": "其实百分之九十的人都搞错了",
                "start": 1.0,
                "end": 4.0,
            }
        ],
    )

    result = _run_cut(cli_runner, fixture_video, output_dir)

    assert result.exit_code == 0, result.output
    assert "warning" in result.output.lower()
    clip = _single_clip(output_dir, fixture_video.stem)
    duration = ffprobe_duration(clip)
    assert abs(duration - 3.0) <= FRAME_TOLERANCE_S


def test_alignment_does_not_modify_highlights_json_on_disk(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _write_transcript(output_dir, fixture_video.stem)
    highlights_path = write_highlights(
        output_dir,
        fixture_video.stem,
        [
            {
                "title": "deviant",
                "reason": "LLM hallucinated the position",
                "quote": "其实百分之九十的人都搞错了",
                "start": 9.8,
                "end": 9.9,
            }
        ],
    )
    before = highlights_path.read_bytes()

    result = _run_cut(cli_runner, fixture_video, output_dir)

    assert result.exit_code == 0, result.output
    assert highlights_path.read_bytes() == before


def test_multi_sentence_highlight_keeps_llm_end_with_buffer(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    """The quote anchors the start; a longer LLM end is kept with buffer.

    Quote matches sentence 2 (4.0-6.0s). LLM span 4.0-8.5s covers sentences
    2-3, so end stays at 8.5 + 0.5 = 9.0s; start = 4.0 - 0.5 = 3.5s.
    """
    output_dir = tmp_path / "output"
    _write_transcript(output_dir, fixture_video.stem)
    write_highlights(
        output_dir,
        fixture_video.stem,
        [
            {
                "title": "two-sentences",
                "reason": "spans two sentences",
                "quote": "其实百分之九十的人都搞错了",
                "start": 4.0,
                "end": 8.5,
            }
        ],
    )

    result = _run_cut(cli_runner, fixture_video, output_dir)

    assert result.exit_code == 0, result.output
    clip = _single_clip(output_dir, fixture_video.stem)
    duration = ffprobe_duration(clip)
    assert abs(duration - 5.5) <= FRAME_TOLERANCE_S


def test_buffer_shrinks_to_avoid_swallowing_neighbour_sentences(
    cli_runner: CliRunner, fixture_video: Path, tmp_path: Path
) -> None:
    """Back-to-back speech: the buffer shrinks to half the gap.

    Gap before sentence 2 (4.0s) is 1.0s → head stays 0.5. Gap after it
    (end 6.0, next begin 7.0) is 1.0s → tail stays 0.5. Synthesize a tight
    transcript instead: sentence 2 at 3.9-6.0 leaves a 0.9s gap before it
    (head = 0.45) and the default 1.0s gap after (tail = 0.5).
    Clip span: 3.45 to 6.5 → duration 3.05s.
    """
    tight = {
        "sentences": [
            {"begin_time": 1.0, "end_time": 3.0, "text": "今天我们讲一个反常识的结论"},
            {"begin_time": 3.9, "end_time": 6.0, "text": "其实百分之九十的人都搞错了"},
            {"begin_time": 7.0, "end_time": 9.0, "text": "最后我们总结一下今天的内容"},
        ],
        "words": [],
    }
    output_dir = tmp_path / "output"
    target_dir = output_dir / fixture_video.stem
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "transcript.json").write_text(
        json.dumps(tight, ensure_ascii=False), encoding="utf-8"
    )
    write_highlights(
        output_dir,
        fixture_video.stem,
        [
            {
                "title": "tight",
                "reason": "neighbours crowd the buffers",
                "quote": "其实百分之九十的人都搞错了",
                "start": 3.9,
                "end": 6.0,
            }
        ],
    )

    result = _run_cut(cli_runner, fixture_video, output_dir)

    assert result.exit_code == 0, result.output
    clip = _single_clip(output_dir, fixture_video.stem)
    duration = ffprobe_duration(clip)
    # ffmpeg's seek lands on frame boundaries; allow two frames of slack.
    assert abs(duration - 3.05) <= 2 * FRAME_TOLERANCE_S