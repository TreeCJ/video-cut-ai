"""Tests for the web UI skeleton at the HTTP seam.

FastAPI TestClient drives the app in-process; assertions cover HTTP
responses and filesystem artifacts only. No network access.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from video_cut import paths
from video_cut.web import create_app


@pytest.fixture()
def output_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated output directory; also isolates from any real .env."""
    monkeypatch.chdir(tmp_path)
    return tmp_path / "output"


@pytest.fixture()
def client(output_dir: Path) -> TestClient:
    return TestClient(create_app(output_dir))


def _create_session(
    output_dir: Path, stem: str, source_path: Path
) -> Path:
    """Stage a pre-existing session mapping + output subdirectory."""
    target_dir = output_dir / stem
    target_dir.mkdir(parents=True, exist_ok=True)
    session_path = target_dir / paths.WEB_SESSION_FILE_NAME
    session_path.write_text(
        json.dumps({"source_path": str(source_path)}, ensure_ascii=False),
        encoding="utf-8",
    )
    return session_path


def test_home_lists_videos_with_existing_sources(
    client: TestClient, output_dir: Path, tmp_path: Path
) -> None:
    source = tmp_path / "talk.mp4"
    source.write_bytes(b"fake")
    _create_session(output_dir, "talk", source)

    response = client.get("/")

    assert response.status_code == 200
    assert "talk" in response.text
    assert f"/videos/talk" in response.text


def test_home_greys_out_entries_whose_source_disappeared(
    client: TestClient, output_dir: Path, tmp_path: Path
) -> None:
    gone = tmp_path / "gone.mp4"
    gone.write_bytes(b"fake")
    _create_session(output_dir, "gone", gone)
    gone.unlink()

    response = client.get("/")

    assert response.status_code == 200
    assert "gone" in response.text
    # 灰显条目：带 missing 标记，且不是可点击链接
    assert "missing" in response.text
    assert 'href="/videos/gone"' not in response.text


def test_home_skips_output_dirs_without_session(
    client: TestClient, output_dir: Path
) -> None:
    (output_dir / "stray").mkdir(parents=True)

    response = client.get("/")

    assert response.status_code == 200
    assert "stray" not in response.text


def test_post_video_creates_session_and_redirects_to_detail(
    client: TestClient, output_dir: Path, tmp_path: Path
) -> None:
    video = tmp_path / "new-video.mp4"
    video.write_bytes(b"fake")

    response = client.post(
        "/videos", data={"video_path": str(video)}, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/videos/new-video"
    session_path = (
        output_dir / "new-video" / paths.WEB_SESSION_FILE_NAME
    )
    assert session_path.exists()
    session = json.loads(session_path.read_text(encoding="utf-8"))
    assert session["source_path"] == str(video)


def test_post_video_with_missing_path_returns_422_with_error(
    client: TestClient, output_dir: Path, tmp_path: Path
) -> None:
    response = client.post(
        "/videos", data={"video_path": str(tmp_path / "nope.mp4")}
    )

    assert response.status_code == 422
    assert "nope.mp4" in response.text
    assert not (output_dir / "nope").exists()


def test_post_video_with_directory_path_returns_422(
    client: TestClient, output_dir: Path, tmp_path: Path
) -> None:
    response = client.post("/videos", data={"video_path": str(tmp_path)})

    assert response.status_code == 422


def test_detail_shows_all_steps_pending_when_no_artifacts(
    client: TestClient, output_dir: Path, tmp_path: Path
) -> None:
    source = tmp_path / "fresh.mp4"
    source.write_bytes(b"fake")
    _create_session(output_dir, "fresh", source)

    response = client.get("/videos/fresh")

    assert response.status_code == 200
    for step in ("extract-audio", "transcribe", "analyze", "cut"):
        assert step in response.text
    for label in ("提取音频", "语音转录", "高光分析", "视频剪辑"):
        assert f'<span class="step-name">{label}</span>' in response.text
    assert response.text.count('status-dot status-pending') == 4
    assert 'status-dot status-done' not in response.text


def test_detail_marks_steps_done_from_existing_artifacts(
    client: TestClient, output_dir: Path, tmp_path: Path
) -> None:
    source = tmp_path / "progress.mp4"
    source.write_bytes(b"fake")
    _create_session(output_dir, "progress", source)
    target_dir = output_dir / "progress"
    (target_dir / paths.AUDIO_FILE_NAME).write_bytes(b"fake-audio")
    (target_dir / paths.TRANSCRIPT_FILE_NAME).write_text(
        json.dumps({"sentences": [], "words": []}), encoding="utf-8"
    )

    response = client.get("/videos/progress")

    assert response.status_code == 200
    assert response.text.count('status-dot status-done') == 2
    assert response.text.count('status-dot status-pending') == 2


def test_detail_marks_cut_done_only_with_clips_and_merged(
    client: TestClient, output_dir: Path, tmp_path: Path
) -> None:
    source = tmp_path / "cutvideo.mp4"
    source.write_bytes(b"fake")
    _create_session(output_dir, "cutvideo", source)
    target_dir = output_dir / "cutvideo"

    response = client.get("/videos/cutvideo")
    assert 'id="step-cut"' in response.text
    # clips 目录存在但 merged.mp4 缺失 → 未完成
    (target_dir / paths.CLIPS_DIR_NAME).mkdir()
    (target_dir / paths.CLIPS_DIR_NAME / "1-a.mp4").write_bytes(b"x")
    response = client.get("/videos/cutvideo")
    assert response.text.count('status-dot status-done') == 0

    (target_dir / paths.MERGED_FILE_NAME).write_bytes(b"x")
    response = client.get("/videos/cutvideo")
    assert response.text.count('status-dot status-done') == 1


def test_detail_404_for_unknown_video(client: TestClient) -> None:
    response = client.get("/videos/ghost")
    assert response.status_code == 404


def test_static_serves_vendored_htmx(client: TestClient) -> None:
    response = client.get("/static/htmx.min.js")
    assert response.status_code == 200
    assert "htmx" in response.text[:200]
