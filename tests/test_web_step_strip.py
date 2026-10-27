"""Tests for the step strip template and status derivation in the web workbench.

HTTP seam only: FastAPI TestClient drives the app in-process; external
services are replaced by the existing env fakes (VIDEO_CUT_ASR_ENGINE_FAKE,
VIDEO_CUT_LLM_PROVIDER_FAKE, VIDEO_CUT_OSS_FAKE_DIR) and ffmpeg runs for real
against the fixture video. No test touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from video_cut import paths
from video_cut.web import create_app
from video_cut.web.session import WebSession, save_session

CLOUD_KEYS = (
    "VIDEO_CUT_DASHSCOPE_API_KEY",
    "VIDEO_CUT_OSS_BUCKET",
    "VIDEO_CUT_OSS_ENDPOINT",
    "VIDEO_CUT_OSS_ACCESS_KEY_ID",
    "VIDEO_CUT_OSS_ACCESS_KEY_SECRET",
    "VIDEO_CUT_LLM_MODEL",
    "VIDEO_CUT_ASR_MODEL",
)

ENGINE_PAYLOAD = {
    "sentences": [
        {"begin_time": 0.5, "end_time": 2.0, "text": "大家好。"},
    ],
    "words": [],
}

CANNED_HIGHLIGHTS = [
    {
        "title": "开场",
        "reason": "理由",
        "quote": "大家好。",
        "start": 0.5,
        "end": 2.0,
    },
]


@pytest.fixture()
def web_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Path]:
    """Scrub real cloud config, then inject fake engine + provider + OSS."""
    for key in CLOUD_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)  # isolate from any real .env in the repo root

    monkeypatch.setenv("VIDEO_CUT_DASHSCOPE_API_KEY", "fake-dashscope-key")
    monkeypatch.setenv("VIDEO_CUT_OSS_BUCKET", "fake-bucket")
    monkeypatch.setenv("VIDEO_CUT_OSS_ENDPOINT", "https://fake-oss.local")
    monkeypatch.setenv("VIDEO_CUT_OSS_ACCESS_KEY_ID", "fake-ak")
    monkeypatch.setenv("VIDEO_CUT_OSS_ACCESS_KEY_SECRET", "fake-sk")

    oss_dir = tmp_path / "fake-oss"
    monkeypatch.setenv("VIDEO_CUT_OSS_FAKE_DIR", str(oss_dir))
    monkeypatch.setenv("VIDEO_CUT_ASR_ENGINE_FAKE", json.dumps(ENGINE_PAYLOAD))
    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps(CANNED_HIGHLIGHTS)
    )

    return {"output_dir": tmp_path / "output", "oss_dir": oss_dir}


@pytest.fixture()
def client(web_env: dict[str, Path]) -> TestClient:
    return TestClient(create_app(web_env["output_dir"]))


def _register_video(client: TestClient, video: Path) -> str:
    response = client.post(
        "/videos", data={"video_path": str(video)}, follow_redirects=False
    )
    assert response.status_code == 303
    return video.stem


def _step_item(html: str, step: str) -> str:
    """Extract the <li> fragment for one step from a step strip."""
    fragment = html.split(f'id="step-{step}"', 1)[1]
    return fragment.split("</li>", 1)[0]


def test_detail_renders_step_strip_with_four_steps(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    assert 'class="step-strip"' in html
    assert 'id="steps"' in html
    for step in ("extract-audio", "transcribe", "analyze", "cut"):
        assert html.count(f'id="step-{step}"') == 1, step


def test_step_trigger_returns_whole_strip(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)

    response = client.post(f"/videos/{stem}/steps/extract-audio")

    assert response.status_code == 202, response.text
    html = response.text
    assert 'class="step-strip"' in html
    item = _step_item(html, "extract-audio")
    assert "status-running" in item


def test_run_to_highlights_returns_whole_strip(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)

    response = client.post(f"/videos/{stem}/run-to-highlights")

    assert response.status_code == 202, response.text
    assert 'class="step-strip"' in response.text


def test_strip_shows_done_for_existing_artifacts(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    target_dir = web_env["output_dir"] / stem
    (target_dir / paths.AUDIO_FILE_NAME).write_bytes(b"fake-audio")

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    assert "status-done" in _step_item(html, "extract-audio")
    for step in ("transcribe", "analyze", "cut"):
        assert "status-pending" in _step_item(html, step), step


def test_strip_analyze_details_contains_prompt(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    target_dir = web_env["output_dir"] / stem
    save_session(
        target_dir,
        WebSession(
            source_path=str(fixture_video), analyze_prompt="找笑点"
        ),
    )

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    item = _step_item(response.text, "analyze")
    assert "<details" in item
    assert "找笑点" in item


def test_strip_step_forms_folded_into_details(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    for step in ("extract-audio", "transcribe", "analyze"):
        item = _step_item(html, step)
        assert "<details" in item, step
        assert f'hx-post="/videos/{stem}/steps/{step}"' in item, step
    # cut 步无触发表单（由两段式 /cut 端点执行）
    cut_item = _step_item(html, "cut")
    assert f'hx-post="/videos/{stem}/steps/cut"' not in cut_item
