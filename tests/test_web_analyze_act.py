"""Tests for the ACT-01 analyze endpoint in the web workbench.

POST /videos/{stem}/analyze: 第一幕「生成高光」入口。有 transcript 时
只跑 analyze；没有时走 run-to-highlights 组合补齐前置步骤。prompt 与
force 透传给步骤。HTTP seam only, no network.
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
    calls_file = tmp_path / "provider-calls.json"
    monkeypatch.setenv("VIDEO_CUT_OSS_FAKE_DIR", str(oss_dir))
    monkeypatch.setenv("_VIDEO_CUT_FAKE_PROVIDER_CALLS_FILE", str(calls_file))
    monkeypatch.setenv("VIDEO_CUT_ASR_ENGINE_FAKE", json.dumps(ENGINE_PAYLOAD))
    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps(CANNED_HIGHLIGHTS)
    )

    return {"output_dir": tmp_path / "output", "calls_file": calls_file}


@pytest.fixture()
def client(web_env: dict[str, Path]) -> TestClient:
    return TestClient(create_app(web_env["output_dir"]))


def _register_video(client: TestClient, video: Path) -> str:
    response = client.post(
        "/videos", data={"video_path": str(video)}, follow_redirects=False
    )
    assert response.status_code == 303
    return video.stem


def _wait_for_last_task(client: TestClient, stem: str) -> dict:
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        tasks = client.get(f"/videos/{stem}/tasks").json()
        if tasks and tasks[-1]["status"] in ("done", "failed", "skipped"):
            return tasks[-1]
        time.sleep(0.05)
    raise AssertionError(f"task did not settle: {tasks}")


def test_analyze_without_transcript_runs_full_chain(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    target_dir = web_env["output_dir"] / stem

    response = client.post(f"/videos/{stem}/analyze", data={"prompt": "找笑点"})

    assert response.status_code == 202, response.text
    task = _wait_for_last_task(client, stem)
    assert task["step"] == "run-to-highlights"
    assert task["status"] == "done"
    assert (target_dir / paths.AUDIO_FILE_NAME).exists()
    assert (target_dir / paths.TRANSCRIPT_FILE_NAME).exists()
    assert (target_dir / paths.HIGHLIGHTS_FILE_NAME).exists()
    calls = json.loads(web_env["calls_file"].read_text(encoding="utf-8"))
    assert calls[0]["user_prompt"] == "找笑点"


def test_analyze_with_transcript_runs_only_analyze(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    target_dir = web_env["output_dir"] / stem

    # 手工放置 transcript：端点应跳过抽音/转录，只跑 analyze。
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / paths.TRANSCRIPT_FILE_NAME).write_text(
        json.dumps(ENGINE_PAYLOAD, ensure_ascii=False), encoding="utf-8"
    )

    response = client.post(f"/videos/{stem}/analyze", data={"prompt": "找笑点"})

    assert response.status_code == 202, response.text
    task = _wait_for_last_task(client, stem)
    assert task["step"] == "analyze"
    assert task["status"] == "done"
    assert not (target_dir / paths.AUDIO_FILE_NAME).exists()
    assert (target_dir / paths.HIGHLIGHTS_FILE_NAME).exists()


def test_analyze_prompt_is_persisted_and_prefilled(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)

    client.post(f"/videos/{stem}/analyze", data={"prompt": "找笑点"})
    _wait_for_last_task(client, stem)

    response = client.get(f"/videos/{stem}")
    assert response.status_code == 200
    assert "找笑点" in response.text
    session = json.loads(
        (web_env["output_dir"] / stem / paths.WEB_SESSION_FILE_NAME).read_text(
            encoding="utf-8"
        )
    )
    assert session["analyze_prompt"] == "找笑点"


def test_detail_has_loading_ui_hooks(client: TestClient, fixture_video: Path) -> None:
    """detail 页给生成/重新生成按钮配等待反馈的挂钩元素。

    生成高光与重新生成是同一按钮同一端点，JS 在点击瞬间切换 loading 态
    （spinner + 已耗时计时），SSE 终态 reload 后弹成功 toast。
    """
    stem = _register_video(client, fixture_video)

    response = client.get(f"/videos/{stem}")
    assert response.status_code == 200
    html = response.text
    # 按钮带 loading 触发约定与 loading 文案。
    assert "data-loading-trigger" in html
    assert 'data-loading-label="AI 分析中"' in html
    # 表单专属错误槽位：409 等错误写入它而不是 alert 兜底。
    assert 'id="trigger-error"' in html
    assert 'data-error-slot' in html
    # toast 容器 + 当前高光条数（成功提示文案的数据源）。
    assert 'id="toast"' in html
    assert 'data-highlight-count="0"' in html


def test_analyze_regenerate_with_force_reruns_only_analyze(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    """「重新生成」按钮带 force=true：只重跑 analyze，上游产物不动。

    回归：按钮渲染为「重新生成」时表单必须发 force，否则 steps 的幂等
    skip 会让任务静默 skipped（highlights.json 已存在），用户看到高光
    没变。端点收到 force 且 transcript 存在时走单步 analyze 而不是
    run-to-highlights 组合任务（组合任务内部 force 固定 False，上游
    永远 skip——若走它，analyze 也会 skip，等于什么都没重跑）。
    """
    stem = _register_video(client, fixture_video)
    client.post(f"/videos/{stem}/analyze", data={"prompt": "first"})
    _wait_for_last_task(client, stem)
    target_dir = web_env["output_dir"] / stem
    audio_before = (target_dir / paths.AUDIO_FILE_NAME).stat().st_mtime
    transcript_before = (target_dir / paths.TRANSCRIPT_FILE_NAME).stat().st_mtime
    calls_file = web_env["calls_file"]
    calls_file.unlink()

    response = client.post(
        f"/videos/{stem}/analyze", data={"prompt": "second", "force": "true"}
    )

    assert response.status_code == 202, response.text
    task = _wait_for_last_task(client, stem)
    assert task["step"] == "analyze"  # 单步，不是 run-to-highlights
    assert task["status"] == "done"
    assert task["detail"] == f"highlights written: {target_dir / paths.HIGHLIGHTS_FILE_NAME}"
    # 上游产物未被重建（时间戳不变），LLM 重新被调用（带新提示词）。
    assert (target_dir / paths.AUDIO_FILE_NAME).stat().st_mtime == audio_before
    assert (target_dir / paths.TRANSCRIPT_FILE_NAME).stat().st_mtime == transcript_before
    calls = json.loads(calls_file.read_text(encoding="utf-8"))
    assert calls[0]["user_prompt"] == "second"


def test_analyze_404_for_unknown_video(client: TestClient) -> None:
    response = client.post("/videos/nope/analyze")
    assert response.status_code == 404


def test_analyze_409_when_busy(
    client: TestClient, fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    client.app.state.task_runner.acquire()  # type: ignore[attr-defined]
    try:
        response = client.post(f"/videos/{stem}/analyze")
    finally:
        client.app.state.task_runner.release()  # type: ignore[attr-defined]
    assert response.status_code == 409
    assert "已有任务在运行" in response.text
