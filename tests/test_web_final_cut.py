"""Tests for the final cut flow in the web workbench.

HTTP seam only, real ffmpeg against the fixture video. The locked split is
the core behavior under test: locked highlights bypass quote alignment and
keep the user's manual boundaries; unlocked highlights go through
align_highlights and their corrections surface in the alignment report.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    ffprobe_audio_stream,
    ffprobe_duration,
    ffprobe_video_stream,
)
from video_cut import paths
from video_cut.web import create_app

FRAME_TOLERANCE_S = 1.0 / 30.0
MERGE_TOLERANCE_S = 0.1

TRANSCRIPT = {
    "sentences": [
        {"begin_time": 1.0, "end_time": 3.0, "text": "大家好，欢迎来到本期视频。"},
        {"begin_time": 4.0, "end_time": 6.0, "text": "其实九成的人都搞错了。"},
        {"begin_time": 7.0, "end_time": 9.0, "text": "记得关注下期节目。"},
    ],
    "words": [],
}

# Highlight 0 is locked: its manual boundaries (0.5-2.0) sit far from its
# quote's actual sentence (1.0-3.0) — align WOULD move it if it were not
# locked. Highlight 1 is unlocked with a start that deviates from the
# quote's sentence begin (7.0) by more than the deviation tolerance, so
# alignment corrects it and reports the move.
DRAFT = [
    {
        "title": "locked-intro",
        "reason": "manual boundaries",
        "quote": "大家好，欢迎来到本期视频。",
        "start": 0.5,
        "end": 2.0,
        "locked": True,
    },
    {
        "title": "deviated outro",
        "reason": "timestamp off",
        "quote": "记得关注下期节目。",
        "start": 1.5,
        "end": 8.0,
        "locked": False,
    },
]


@pytest.fixture()
def studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """An app whose video has transcript + draft + highlights on disk."""
    monkeypatch.chdir(tmp_path)  # isolate from any real .env in the repo root

    output_dir = tmp_path / "output"
    target_dir = output_dir / "fixture"
    target_dir.mkdir(parents=True)
    (target_dir / paths.WEB_SESSION_FILE_NAME).write_text(
        json.dumps({"source_path": "__VIDEO__"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (target_dir / paths.TRANSCRIPT_FILE_NAME).write_text(
        json.dumps(TRANSCRIPT, ensure_ascii=False), encoding="utf-8"
    )
    (target_dir / paths.HIGHLIGHTS_FILE_NAME).write_text(
        json.dumps(
            [{k: v for k, v in item.items() if k != "locked"} for item in DRAFT],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (target_dir / paths.HIGHLIGHTS_DRAFT_FILE_NAME).write_text(
        json.dumps(DRAFT, ensure_ascii=False), encoding="utf-8"
    )
    return {"output_dir": output_dir, "stem": "fixture", "target_dir": target_dir}


@pytest.fixture()
def client(
    studio: dict[str, Path], fixture_video: Path
) -> TestClient:
    session_path = studio["target_dir"] / paths.WEB_SESSION_FILE_NAME
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["source_path"] = str(fixture_video)
    session_path.write_text(json.dumps(session), encoding="utf-8")
    return TestClient(create_app(studio["output_dir"]))


def _wait_for_last_task(client: TestClient, stem: str) -> dict:
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        tasks = client.get(f"/videos/{stem}/tasks").json()
        if tasks and tasks[-1]["status"] in ("done", "failed", "skipped"):
            return tasks[-1]
        time.sleep(0.05)
    raise AssertionError(f"task did not settle: {tasks}")


def _request_report(client: TestClient, stem: str) -> dict:
    response = client.post(f"/videos/{stem}/cut")
    assert response.status_code == 200, response.text
    return client.get(f"/videos/{stem}/cut/report").json()


def _confirm_cut(client: TestClient, stem: str) -> dict:
    response = client.post(f"/videos/{stem}/cut", data={"confirm": "true"})
    assert response.status_code == 202, response.text
    return _wait_for_last_task(client, stem)


def test_alignment_report_contains_correction_for_deviated_unlocked_highlight(
    client: TestClient, studio: dict[str, Path]
) -> None:
    report = _request_report(client, studio["stem"])

    assert report["status"] == "pending"
    items = {entry["title"]: entry for entry in report["items"]}
    deviated = items["deviated outro"]
    assert deviated["locked"] is False
    assert deviated["moved"] is True
    assert deviated["original_start"] == 1.5
    # Aligned start: sentence begin 7.0 minus adaptive head buffer
    # (gap to previous sentence end 6.0 is 1.0s, half-gap 0.5 = BUFFER_S).
    assert abs(deviated["final_start"] - 6.5) <= 0.01
    assert deviated["warning"]


def test_alignment_report_keeps_locked_highlight_verbatim(
    client: TestClient, studio: dict[str, Path]
) -> None:
    report = _request_report(client, studio["stem"])

    items = {entry["title"]: entry for entry in report["items"]}
    locked = items["locked-intro"]
    assert locked["locked"] is True
    assert locked["moved"] is False
    assert locked["original_start"] == 0.5
    assert locked["final_start"] == 0.5
    assert locked["final_end"] == 2.0


def test_requesting_report_does_not_cut_anything(
    client: TestClient, studio: dict[str, Path]
) -> None:
    _request_report(client, studio["stem"])

    target_dir = studio["target_dir"]
    assert not (target_dir / paths.CLIPS_DIR_NAME).exists()
    assert not (target_dir / paths.MERGED_FILE_NAME).exists()
    assert client.get(f"/videos/{studio['stem']}/tasks").json() == []


def test_confirmed_cut_produces_clips_and_merged_with_uniform_encoding(
    client: TestClient, studio: dict[str, Path]
) -> None:
    task = _confirm_cut(client, studio["stem"])

    assert task["status"] == "done", task["error"]
    target_dir = studio["target_dir"]
    clips_dir = target_dir / paths.CLIPS_DIR_NAME
    clip_paths = sorted(clips_dir.glob("*.mp4"))
    assert [p.name for p in clip_paths] == [
        "01-locked-intro.mp4",
        "02-deviated outro.mp4",
    ]
    merged = target_dir / paths.MERGED_FILE_NAME
    assert merged.exists()

    for clip in clip_paths:
        video_stream = ffprobe_video_stream(clip)
        assert video_stream["codec_name"] == "h264"
        assert video_stream["pix_fmt"] == "yuv420p"
        assert video_stream["r_frame_rate"] == "30/1"
        audio_stream = ffprobe_audio_stream(clip)
        assert audio_stream["codec_name"] == "aac"
        assert audio_stream["sample_rate"] == "48000"
        assert audio_stream["channels"] == 2

    expected = sum(ffprobe_duration(clip) for clip in clip_paths)
    assert abs(ffprobe_duration(merged) - expected) <= MERGE_TOLERANCE_S


def test_locked_clip_duration_matches_manual_boundaries_unlocked_matches_aligned(
    client: TestClient, studio: dict[str, Path]
) -> None:
    task = _confirm_cut(client, studio["stem"])
    assert task["status"] == "done", task["error"]

    clips_dir = studio["target_dir"] / paths.CLIPS_DIR_NAME
    locked_clip = clips_dir / "01-locked-intro.mp4"
    unlocked_clip = clips_dir / "02-deviated outro.mp4"

    # Locked: align must NOT have moved it — duration equals the manual
    # 0.5-2.0 range, not the quote sentence's 1.0-3.0 range.
    assert abs(ffprobe_duration(locked_clip) - 1.5) <= FRAME_TOLERANCE_S

    # Unlocked: aligned to sentence 7.0-9.0 with adaptive buffers
    # (head 0.5 clamped by the 1.0s gap, tail 0.5 to the video end).
    # final = 6.5 .. max(8.0, 9.0) + 0.5 = 9.5 -> duration 3.0s.
    assert abs(ffprobe_duration(unlocked_clip) - 3.0) <= FRAME_TOLERANCE_S


def test_recut_after_draft_edit_replaces_old_artifacts(
    client: TestClient, studio: dict[str, Path]
) -> None:
    task = _confirm_cut(client, studio["stem"])
    assert task["status"] == "done", task["error"]
    clips_dir = studio["target_dir"] / paths.CLIPS_DIR_NAME
    first_clip = clips_dir / "01-locked-intro.mp4"
    first_mtime = first_clip.stat().st_mtime_ns
    old_duration = ffprobe_duration(first_clip)

    # Edit the locked highlight's boundaries, then re-cut.
    response = client.post(
        f"/videos/{studio['stem']}/highlights/0/boundaries",
        data={"start": "0.5", "end": "3.5"},
    )
    assert response.status_code == 200
    time.sleep(0.01)
    task = _confirm_cut(client, studio["stem"])
    assert task["status"] == "done", task["error"]

    assert first_clip.stat().st_mtime_ns > first_mtime
    new_duration = ffprobe_duration(first_clip)
    assert abs(new_duration - 3.0) <= FRAME_TOLERANCE_S
    assert abs(new_duration - old_duration) > 0.5


def test_clips_and_merged_are_served_for_playback(
    client: TestClient, studio: dict[str, Path]
) -> None:
    task = _confirm_cut(client, studio["stem"])
    assert task["status"] == "done", task["error"]
    stem = studio["stem"]

    for name in ("01-locked-intro.mp4", "02-deviated outro.mp4"):
        response = client.get(f"/videos/{stem}/clips/{name}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "video/mp4"
        assert len(response.content) > 0

    merged = client.get(f"/videos/{stem}/merged")
    assert merged.status_code == 200
    assert len(merged.content) > 0


def test_detail_page_lists_clips_and_merged_player_after_cut(
    client: TestClient, studio: dict[str, Path]
) -> None:
    task = _confirm_cut(client, studio["stem"])
    assert task["status"] == "done", task["error"]

    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    html = response.text
    assert "01-locked-intro.mp4" in html
    assert "02-deviated outro.mp4" in html
    assert "merged.mp4" in html
    assert f"/videos/{studio['stem']}/merged" in html


def test_cut_without_highlights_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture_video: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output"
    target_dir = output_dir / fixture_video.stem
    target_dir.mkdir(parents=True)
    (target_dir / paths.WEB_SESSION_FILE_NAME).write_text(
        json.dumps({"source_path": str(fixture_video)}, ensure_ascii=False),
        encoding="utf-8",
    )
    client = TestClient(create_app(output_dir))

    response = client.post(f"/videos/{fixture_video.stem}/cut")

    assert response.status_code == 409


def test_cut_step_status_shows_done_after_confirm(
    client: TestClient, studio: dict[str, Path]
) -> None:
    task = _confirm_cut(client, studio["stem"])
    assert task["status"] == "done", task["error"]
    assert task["step"] == "cut"

    response = client.get(f"/videos/{studio['stem']}")
    assert response.status_code == 200
    assert 'id="step-cut"' in response.text
    assert "status-done" in response.text
