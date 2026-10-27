"""Tests for the workbench layout of the detail page.

HTTP seam only: structural assertions against the rendered HTML source
(element presence and source order), no browser. Layout contract:

  <div class="acts">   (act-generate prompt + step strip)
                       (act-review: video + filmstrip + highlight cards + transcript)
                       (act-master: #final-cut)
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
    ],
    "words": [],
}

HIGHLIGHTS = [
    {
        "title": "开场反转",
        "reason": "前30秒抛出反常识结论",
        "quote": "其实90%的人都搞错了。",
        "start": 2.5,
        "end": 5.0,
    }
]


@pytest.fixture()
def web_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Scrub real cloud config; isolate from any real .env in the repo root."""
    for key in CLOUD_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    return {"output_dir": tmp_path / "output"}


@pytest.fixture()
def client(web_env: dict[str, Path]) -> TestClient:
    return TestClient(create_app(web_env["output_dir"]))


def _register(client: TestClient, video: Path) -> str:
    response = client.post(
        "/videos", data={"video_path": str(video)}, follow_redirects=False
    )
    assert response.status_code == 303
    return video.stem


def _write_transcript(web_env: dict[str, Path], stem: str) -> None:
    transcript_path = web_env["output_dir"] / stem / paths.TRANSCRIPT_FILE_NAME
    transcript_path.write_text(
        json.dumps(TRANSCRIPT_PAYLOAD, ensure_ascii=False), encoding="utf-8"
    )


def _write_highlights(web_env: dict[str, Path], stem: str) -> None:
    highlights_path = web_env["output_dir"] / stem / paths.HIGHLIGHTS_FILE_NAME
    highlights_path.write_text(
        json.dumps(HIGHLIGHTS, ensure_ascii=False), encoding="utf-8"
    )


def test_detail_renders_three_acts_in_order(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register(client, fixture_video)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    assert 'class="acts"' in html
    assert 'id="act-generate"' in html
    assert 'id="act-review"' in html
    assert 'id="act-master"' in html
    generate_pos = html.index('id="act-generate"')
    review_pos = html.index('id="act-review"')
    master_pos = html.index('id="act-master"')
    assert generate_pos < review_pos < master_pos
    # 审看幕：视频在步骤条之后（步骤条属于第一幕），高光卡在视频之后。
    video_pos = html.index('id="source-video"')
    strip_pos = html.index('id="steps"')
    highlights_pos = html.index('id="highlight-cards"')
    assert strip_pos < video_pos < highlights_pos
    # 胶片条随视频出现。
    assert 'id="filmstrip"' in html


def test_detail_analyze_button_posts_to_analyze_endpoint(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register(client, fixture_video)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    assert f'hx-post="/videos/{stem}/analyze"' in response.text
    assert 'hx-target="#steps"' in response.text


def test_detail_transcript_wrapped_in_collapsible(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register(client, fixture_video)
    _write_transcript(web_env, stem)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    assert 'id="transcript-wrap"' in html
    wrap_pos = html.index('id="transcript-wrap"')
    sentence_list_pos = html.index('class="transcript sentence-list"')
    assert wrap_pos < sentence_list_pos


def test_detail_without_transcript_omits_transcript_wrap(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register(client, fixture_video)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    assert 'id="transcript-wrap"' not in response.text


def test_detail_without_source_omits_video_but_keeps_acts(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register(client, fixture_video)
    fixture_video.unlink()

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    assert 'id="source-video"' not in html
    assert 'id="act-review"' in html
    assert f'hx-post="/videos/{stem}/analyze"' in html


def test_detail_empty_highlights_shows_guide(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register(client, fixture_video)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    assert 'id="highlight-cards"' in html
    assert "生成高光" in html


def test_detail_final_cut_section_after_highlights(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register(client, fixture_video)
    _write_highlights(web_env, stem)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    highlights_pos = html.index('id="highlight-cards"')
    final_cut_pos = html.index('id="final-cut"')
    assert highlights_pos < final_cut_pos
