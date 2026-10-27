"""Tests for the transcript view: sentence list + source video Range streaming.

HTTP seam only: the sentence list on the detail page is asserted against
transcript.json content/order; the source video endpoint is asserted at the
byte level (Range request -> 206 + correct bytes; full GET -> 200). Click-to-
seek is frontend behavior carried by data attributes on the timecode cells,
asserted here as HTML, not via a browser.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from video_cut import paths
from video_cut.web import create_app

CLOUD_KEYS = (
    "VIDEO_CUT_DASHSCOPE_API_KEY",
    "VIDEO_CUT_OSS_BUCKET",
    "VIDEO_CUT_OSS_ENDPOINT",
    "VIDEO_CUT_OSS_ACCESS_KEY_ID",
    "VIDEO_CUT_OSS_ACCESS_KEY_SECRET",
    "VIDEO_CUT_LLM_MODEL",
    "VIDEO_CUT_ASR_MODEL",
)

TRANSCRIPT_PAYLOAD = {
    "sentences": [
        {"begin_time": 0.5, "end_time": 2.0, "text": "大家好，欢迎来到本期视频。"},
        {"begin_time": 2.5, "end_time": 5.0, "text": "其实90%的人都搞错了。"},
        {"begin_time": 5.5, "end_time": 9.0, "text": "今天我们把这个问题讲透。"},
    ],
    "words": [],
}


@pytest.fixture()
def web_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Scrub real cloud config; isolate from any real .env in the repo root."""
    for key in CLOUD_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output"
    return {"output_dir": output_dir}


@pytest.fixture()
def client(web_env: dict[str, Path]) -> TestClient:
    return TestClient(create_app(web_env["output_dir"]))


@pytest.fixture()
def video_with_transcript(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> str:
    """Register a workflow and plant a transcript.json; return the stem."""
    response = client.post(
        "/videos",
        data={"video_path": str(fixture_video)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    stem = fixture_video.stem
    target_dir = web_env["output_dir"] / stem
    transcript_path = target_dir / paths.TRANSCRIPT_FILE_NAME
    transcript_path.write_text(
        json.dumps(TRANSCRIPT_PAYLOAD, ensure_ascii=False), encoding="utf-8"
    )
    return stem


def test_detail_page_renders_sentence_list_matching_transcript_json(
    client: TestClient, video_with_transcript: str
) -> None:
    response = client.get(f"/videos/{video_with_transcript}")

    assert response.status_code == 200
    body = response.text
    positions: list[int] = []
    for index, sentence in enumerate(TRANSCRIPT_PAYLOAD["sentences"]):
        assert sentence["text"] in body
        positions.append(body.index(sentence["text"]))
        # timecode carries begin_time as a data attribute for click-to-seek
        marker = f'data-begin-time="{sentence["begin_time"]}"'
        assert marker in body, f"missing seek marker for sentence {index}"
    assert positions == sorted(positions), "sentences must render in file order"


def test_detail_page_embeds_video_player_pointing_at_source_endpoint(
    client: TestClient, video_with_transcript: str
) -> None:
    response = client.get(f"/videos/{video_with_transcript}")

    assert response.status_code == 200
    assert "<video" in response.text
    assert f"/videos/{video_with_transcript}/source" in response.text


def test_detail_page_without_transcript_omits_sentence_list(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    response = client.post(
        "/videos",
        data={"video_path": str(fixture_video)},
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = client.get(f"/videos/{fixture_video.stem}")

    assert detail.status_code == 200
    assert "大家好" not in detail.text


def test_source_video_full_get_returns_200_with_video_bytes(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    client.post(
        "/videos",
        data={"video_path": str(fixture_video)},
        follow_redirects=False,
    )

    response = client.get(f"/videos/{fixture_video.stem}/source")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/")
    assert response.content == fixture_video.read_bytes()


def test_source_video_range_request_returns_206_with_correct_bytes(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    client.post(
        "/videos",
        data={"video_path": str(fixture_video)},
        follow_redirects=False,
    )
    total = fixture_video.stat().st_size
    start, end = 100, 1099

    response = client.get(
        f"/videos/{fixture_video.stem}/source",
        headers={"Range": f"bytes={start}-{end}"},
    )

    assert response.status_code == 206
    assert (
        response.headers["content-range"] == f"bytes {start}-{end}/{total}"
    )
    expected = fixture_video.read_bytes()[start : end + 1]
    assert response.content == expected


def test_source_video_unknown_stem_returns_404(client: TestClient) -> None:
    response = client.get("/videos/nonexistent/source")

    assert response.status_code == 404


def test_source_video_missing_file_returns_404(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    client.post(
        "/videos",
        data={"video_path": str(fixture_video)},
        follow_redirects=False,
    )
    fixture_video.unlink()

    response = client.get(f"/videos/{fixture_video.stem}/source")

    assert response.status_code == 404
