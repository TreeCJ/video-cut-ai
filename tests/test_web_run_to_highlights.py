"""Tests for the run-to-highlights combo endpoint in the web workbench.

HTTP seam only: FastAPI TestClient drives the app in-process; external
services are replaced by the existing env fakes (VIDEO_CUT_ASR_ENGINE_FAKE,
VIDEO_CUT_LLM_PROVIDER_FAKE, VIDEO_CUT_OSS_FAKE_DIR) and ffmpeg runs for real
against the fixture video. No test touches the network.
"""

from __future__ import annotations

import json
import time
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

ENGINE_PAYLOAD = {
    "sentences": [
        {"begin_time": 0.5, "end_time": 2.0, "text": "大家好，欢迎来到本期视频。"},
        {"begin_time": 2.5, "end_time": 5.0, "text": "其实90%的人都搞错了。"},
        {"begin_time": 5.5, "end_time": 9.0, "text": "今天我们把这个问题讲透。"},
    ],
    "words": [
        {"begin_time": 0.5, "end_time": 0.8, "word": "大家"},
        {"begin_time": 2.5, "end_time": 2.8, "word": "其实"},
    ],
}

CANNED_HIGHLIGHTS = [
    {
        "title": "开场反转",
        "reason": "前30秒抛出反常识结论",
        "quote": "其实90%的人都搞错了。",
        "start": 2.5,
        "end": 5.0,
    },
    {
        "title": "收尾承诺",
        "reason": "信息密度高，预告全片价值",
        "quote": "今天我们把这个问题讲透。",
        "start": 5.5,
        "end": 9.0,
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
    calls_file = tmp_path / "provider-calls.json"
    monkeypatch.setenv("VIDEO_CUT_OSS_FAKE_DIR", str(oss_dir))
    monkeypatch.setenv("_VIDEO_CUT_FAKE_PROVIDER_CALLS_FILE", str(calls_file))
    monkeypatch.setenv("VIDEO_CUT_ASR_ENGINE_FAKE", json.dumps(ENGINE_PAYLOAD))
    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps(CANNED_HIGHLIGHTS)
    )

    output_dir = tmp_path / "output"
    return {
        "output_dir": output_dir,
        "oss_dir": oss_dir,
        "calls_file": calls_file,
    }


@pytest.fixture()
def client(web_env: dict[str, Path]) -> TestClient:
    return TestClient(create_app(web_env["output_dir"]))


def _register_video(client: TestClient, video: Path) -> str:
    """Create a workflow for a real video file; return its stem."""
    response = client.post(
        "/videos", data={"video_path": str(video)}, follow_redirects=False
    )
    assert response.status_code == 303
    return video.stem


def _run_to_highlights(client: TestClient, stem: str) -> dict:
    """POST the combo endpoint and wait for the task to settle."""
    response = client.post(f"/videos/{stem}/run-to-highlights")
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        tasks = client.get(f"/videos/{stem}/tasks").json()
        if tasks and tasks[-1]["status"] in ("done", "failed", "skipped"):
            return tasks[-1]
        time.sleep(0.05)
    raise AssertionError(f"task did not settle: {tasks}")


def _run_step(client: TestClient, stem: str, step: str, **form: str) -> dict:
    """Trigger a single step and wait for the task to settle."""
    response = client.post(f"/videos/{stem}/steps/{step}", data=form)
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        tasks = client.get(f"/videos/{stem}/tasks").json()
        if tasks and tasks[-1]["status"] in ("done", "failed", "skipped"):
            return tasks[-1]
        time.sleep(0.05)
    raise AssertionError(f"task did not settle: {tasks}")


def test_run_to_highlights_runs_three_steps_in_order(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    target_dir = web_env["output_dir"] / stem

    task = _run_to_highlights(client, stem)

    assert task["step"] == "run-to-highlights"
    assert task["status"] == "done"
    assert (target_dir / paths.AUDIO_FILE_NAME).exists()
    assert (target_dir / paths.TRANSCRIPT_FILE_NAME).exists()
    assert (target_dir / paths.HIGHLIGHTS_FILE_NAME).exists()


def test_run_to_highlights_skips_existing_artifacts(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    target_dir = web_env["output_dir"] / stem

    _run_step(client, stem, "extract-audio")
    audio_path = target_dir / paths.AUDIO_FILE_NAME
    audio_mtime = audio_path.stat().st_mtime_ns

    task = _run_to_highlights(client, stem)

    assert task["status"] == "done"
    assert "skipped" in task["detail"]
    assert audio_path.stat().st_mtime_ns == audio_mtime


def test_run_to_highlights_stops_on_failure(
    client: TestClient,
    web_env: dict[str, Path],
    fixture_video: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps({"raw_text": "not json"})
    )
    stem = _register_video(client, fixture_video)
    target_dir = web_env["output_dir"] / stem

    task = _run_to_highlights(client, stem)

    assert task["status"] == "failed"
    assert (target_dir / paths.AUDIO_FILE_NAME).exists()
    assert (target_dir / paths.TRANSCRIPT_FILE_NAME).exists()
    assert not (target_dir / paths.HIGHLIGHTS_FILE_NAME).exists()


def test_run_to_highlights_resumes_after_failure(
    client: TestClient,
    web_env: dict[str, Path],
    fixture_video: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stem = _register_video(client, fixture_video)
    target_dir = web_env["output_dir"] / stem

    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps({"raw_text": "not json"})
    )
    failed_task = _run_to_highlights(client, stem)
    assert failed_task["status"] == "failed"

    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps(CANNED_HIGHLIGHTS)
    )
    task = _run_to_highlights(client, stem)

    assert task["status"] == "done"
    assert (target_dir / paths.HIGHLIGHTS_FILE_NAME).exists()


def test_run_to_highlights_returns_409_when_busy(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    client.app.state.task_runner.acquire()  # type: ignore[attr-defined]
    try:
        response = client.post(f"/videos/{stem}/run-to-highlights")
    finally:
        client.app.state.task_runner.release()  # type: ignore[attr-defined]
    assert response.status_code == 409


def test_run_to_highlights_404_for_unknown_video(client: TestClient) -> None:
    response = client.post("/videos/nope/run-to-highlights")
    assert response.status_code == 404


def test_run_to_highlights_failure_visible_on_detail_page(
    client: TestClient,
    web_env: dict[str, Path],
    fixture_video: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """combo 任务失败时，错误信息应落在第一个未完成步骤的卡片上。"""
    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps({"raw_text": "not json"})
    )
    stem = _register_video(client, fixture_video)

    task = _run_to_highlights(client, stem)
    assert task["status"] == "failed"

    response = client.get(f"/videos/{stem}")
    assert response.status_code == 200
    # analyze 是第一个未完成步骤（extract-audio 和 transcribe 已成功），
    # 错误应显示在 step-analyze 上。
    assert 'id="step-analyze"' in response.text
    # 找到 step-analyze 元素片段并断言其包含失败状态与错误文本
    import re
    match = re.search(
        r'<li[^>]*id="step-analyze"[^>]*>(.*?)</li>', response.text, re.DOTALL
    )
    assert match, "step-analyze element not found"
    fragment = match.group(1)
    assert "status-failed" in fragment
    assert "error-summary" in fragment


def test_run_to_highlights_409_body_contains_error_text(
    client: TestClient, fixture_video: Path
) -> None:
    """409 响应体应包含错误文本（供 JS htmx:responseError 读取展示）。"""
    stem = _register_video(client, fixture_video)
    client.app.state.task_runner.acquire()  # type: ignore[attr-defined]
    try:
        response = client.post(f"/videos/{stem}/run-to-highlights")
    finally:
        client.app.state.task_runner.release()  # type: ignore[attr-defined]
    assert response.status_code == 409
    assert "已有任务在运行" in response.text
