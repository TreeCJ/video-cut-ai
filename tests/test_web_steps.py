"""Tests for transcribe/analyze step wiring in the web workbench.

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


def _run_step(client: TestClient, stem: str, step: str, **form: str) -> dict:
    """Trigger a step and wait for the task to settle; return the final state."""
    response = client.post(f"/videos/{stem}/steps/{step}", data=form)
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        tasks = client.get(f"/videos/{stem}/tasks").json()
        if tasks and tasks[-1]["status"] in ("done", "failed", "skipped"):
            return tasks[-1]
        time.sleep(0.05)
    raise AssertionError(f"task did not settle: {tasks}")


def test_full_chain_produces_cli_parity_artifacts(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    target_dir = web_env["output_dir"] / stem

    audio_task = _run_step(client, stem, "extract-audio")
    assert audio_task["status"] == "done"
    assert (target_dir / paths.AUDIO_FILE_NAME).exists()

    transcribe_task = _run_step(client, stem, "transcribe")
    assert transcribe_task["status"] == "done"
    transcript_path = target_dir / paths.TRANSCRIPT_FILE_NAME
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert transcript == ENGINE_PAYLOAD

    analyze_task = _run_step(client, stem, "analyze")
    assert analyze_task["status"] == "done"
    highlights_path = target_dir / paths.HIGHLIGHTS_FILE_NAME
    highlights = json.loads(highlights_path.read_text(encoding="utf-8"))
    assert highlights == CANNED_HIGHLIGHTS


def test_analyze_custom_prompt_reaches_the_provider(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    _run_step(client, stem, "extract-audio")
    _run_step(client, stem, "transcribe")

    _run_step(client, stem, "analyze", prompt="找反转和笑点")

    calls = json.loads(web_env["calls_file"].read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert calls[0]["user_prompt"] == "找反转和笑点"


def test_force_rerun_prefills_last_submitted_prompt(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    _run_step(client, stem, "extract-audio")
    _run_step(client, stem, "transcribe")
    _run_step(client, stem, "analyze", prompt="找反转和笑点")

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    assert "找反转和笑点" in response.text
    session_path = (
        web_env["output_dir"] / stem / paths.WEB_SESSION_FILE_NAME
    )
    session = json.loads(session_path.read_text(encoding="utf-8"))
    assert session["analyze_prompt"] == "找反转和笑点"


def test_transcribe_without_audio_fails_with_missing_artifact_error(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)

    task = _run_step(client, stem, "transcribe")

    assert task["status"] == "failed"
    assert paths.AUDIO_FILE_NAME in task["error"]
    response = client.get(f"/videos/{stem}")
    assert paths.AUDIO_FILE_NAME in response.text


def test_analyze_without_transcript_fails_with_missing_artifact_error(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)

    task = _run_step(client, stem, "analyze")

    assert task["status"] == "failed"
    assert paths.TRANSCRIPT_FILE_NAME in task["error"]
    response = client.get(f"/videos/{stem}")
    assert paths.TRANSCRIPT_FILE_NAME in response.text


def test_existing_artifacts_skip_and_provider_not_recalled(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    _run_step(client, stem, "extract-audio")
    _run_step(client, stem, "transcribe")
    _run_step(client, stem, "analyze")
    calls_file = web_env["calls_file"]
    calls_file.unlink()

    transcribe_task = _run_step(client, stem, "transcribe")
    analyze_task = _run_step(client, stem, "analyze")

    assert transcribe_task["status"] == "skipped"
    assert analyze_task["status"] == "skipped"
    assert not calls_file.exists()


def test_force_rerun_recreates_artifacts_and_recals_provider(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    _run_step(client, stem, "extract-audio")
    _run_step(client, stem, "transcribe")
    _run_step(client, stem, "analyze", prompt="first")
    calls_file = web_env["calls_file"]
    calls_file.unlink()

    task = _run_step(
        client, stem, "analyze", force="true", prompt="second prompt"
    )

    assert task["status"] == "done"
    calls = json.loads(calls_file.read_text(encoding="utf-8"))
    assert calls[0]["user_prompt"] == "second prompt"
