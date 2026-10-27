"""Tests for the web task runner: single-task lock, SSE, extract-audio wiring.

HTTP seam only: FastAPI TestClient drives the app in-process; ffmpeg runs
for real against the fixture video. Assertions cover HTTP responses, SSE
event shapes, and filesystem artifacts — never runner internals.
"""

from __future__ import annotations

import json
import subprocess
import time
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


def _register_video(client: TestClient, video: Path) -> str:
    """Create a workflow for a real video file; return its stem."""
    response = client.post(
        "/videos", data={"video_path": str(video)}, follow_redirects=False
    )
    assert response.status_code == 303
    return video.stem


def _wait_terminal(
    client: TestClient, stem: str, timeout: float = 30.0
) -> dict:
    """Poll the status endpoint until the latest task for a step settles."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/videos/{stem}/tasks")
        assert response.status_code == 200
        tasks = response.json()
        if tasks and tasks[-1]["status"] in ("done", "failed", "skipped"):
            return tasks[-1]
        time.sleep(0.05)
    raise AssertionError(f"task did not settle within {timeout}s: {tasks}")


def _read_sse_events(
    url: str, max_events: int = 10, timeout: float = 30.0
) -> list[dict]:
    """Read SSE events from a live server until a terminal task event arrives."""
    import httpx

    events: list[dict] = []
    with httpx.Client(timeout=timeout) as http:
        with http.stream("GET", url) as response:
            assert response.status_code == 200
            event: dict[str, str] = {}
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event["event"] = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    event["data"] = line.split(":", 1)[1].strip()
                elif line == "" and event:
                    events.append(event)
                    if event["event"] == "task":
                        status = json.loads(event["data"])["status"]
                        if status in ("done", "failed", "skipped"):
                            return events
                    event = {}
                    if len(events) >= max_events:
                        break
    return events


def test_extract_audio_runs_and_produces_artifact(
    client: TestClient, output_dir: Path, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)

    response = client.post(f"/videos/{stem}/steps/extract-audio")

    assert response.status_code == 202
    task = _wait_terminal(client, stem)
    assert task["step"] == "extract-audio"
    assert task["status"] == "done"
    audio_path = output_dir / stem / paths.AUDIO_FILE_NAME
    assert audio_path.exists()
    # 真产物：m4a 容器里一条 AAC 音轨
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name", "-of", "json",
            str(audio_path),
        ],
        check=True, capture_output=True, text=True,
    )
    assert json.loads(probe.stdout)["streams"][0]["codec_name"] == "aac"


def test_detail_shows_step_done_after_task_completes(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    client.post(f"/videos/{stem}/steps/extract-audio")
    _wait_terminal(client, stem)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    assert 'status-dot status-done' in response.text


def test_existing_artifact_skips_without_force(
    client: TestClient, output_dir: Path, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    target_dir = output_dir / stem
    marker = target_dir / paths.AUDIO_FILE_NAME
    marker.write_bytes(b"pre-existing")
    mtime = marker.stat().st_mtime_ns

    client.post(f"/videos/{stem}/steps/extract-audio")
    task = _wait_terminal(client, stem)

    assert task["status"] == "skipped"
    # 未重跑：文件内容与修改时间不变
    assert marker.read_bytes() == b"pre-existing"
    assert marker.stat().st_mtime_ns == mtime


def test_force_reruns_despite_existing_artifact(
    client: TestClient, output_dir: Path, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    marker = output_dir / stem / paths.AUDIO_FILE_NAME
    marker.write_bytes(b"pre-existing")

    client.post(f"/videos/{stem}/steps/extract-audio", data={"force": "true"})
    task = _wait_terminal(client, stem)

    assert task["status"] == "done"
    assert marker.read_bytes() != b"pre-existing"


def test_409_while_another_task_is_running(
    client: TestClient, output_dir: Path, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    # 人为占住任务锁，模拟运行中的任务
    client.app.state.task_runner.acquire()  # type: ignore[attr-defined]
    try:
        response = client.post(f"/videos/{stem}/steps/extract-audio")
    finally:
        client.app.state.task_runner.release()  # type: ignore[attr-defined]

    assert response.status_code == 409


def test_failure_surfaces_error_summary(
    client: TestClient, tmp_path: Path
) -> None:
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"this is not a video")
    stem = _register_video(client, broken)

    client.post(f"/videos/{stem}/steps/extract-audio")
    task = _wait_terminal(client, stem)

    assert task["status"] == "failed"
    assert task["error"]
    assert "ffmpeg" in task["error"] or "error" in task["error"].lower()

    response = client.get(f"/videos/{stem}")
    assert 'status-dot status-failed' in response.text


def test_sse_pushes_running_then_done(
    output_dir: Path, fixture_video: Path
) -> None:
    """SSE 走真实 HTTP：TestClient 的共享 portal 不支持并发流式响应。"""
    import concurrent.futures
    import socket
    import threading

    import httpx
    import uvicorn

    app = create_app(output_dir)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if time.monotonic() > deadline:
                raise AssertionError("uvicorn did not start")
            time.sleep(0.05)

        with httpx.Client(base_url=base, timeout=30) as http:
            response = http.post(
                "/videos", data={"video_path": str(fixture_video)}
            )
            assert response.status_code == 303

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                reader = pool.submit(_read_sse_events, f"{base}/events")
                # 等 SSE 连接建立后再触发任务
                time.sleep(0.3)
                response = http.post(
                    f"/videos/{fixture_video.stem}/steps/extract-audio"
                )
                assert response.status_code == 202
                events = reader.result(timeout=30)
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    kinds = [e["event"] for e in events]
    assert kinds[0] == "snapshot"
    task_events = [e for e in events if e["event"] == "task"]
    statuses = [json.loads(e["data"])["status"] for e in task_events]
    assert "running" in statuses
    assert statuses[-1] == "done"
    assert statuses.index("running") < len(statuses) - 1
    payload = json.loads(task_events[-1]["data"])
    assert payload["step"] == "extract-audio"


def test_detail_page_disables_buttons_while_task_running(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    client.app.state.task_runner.acquire()  # type: ignore[attr-defined]
    try:
        response = client.get(f"/videos/{stem}")
    finally:
        client.app.state.task_runner.release()  # type: ignore[attr-defined]

    assert response.status_code == 200
    assert "disabled" in response.text
