"""Tests for the code-review fixes on the web workbench.

Covers: analyze prompt persistence on skip, draft reset on force re-analyze,
dead cut-card trigger form removal, stored-plan confirm semantics (409 on
stale report), SSE pending broadcast, TaskRunner snapshot/acquire cleanup,
and WebSession typing. HTTP seam only, no network.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from video_cut import paths
from video_cut.web import create_app
from video_cut.web.session import WebSession
from video_cut.web.tasks import TaskRunner

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
    "words": [],
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
def web_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
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


def _run_step(client: TestClient, stem: str, step: str, **form: str) -> dict:
    response = client.post(f"/videos/{stem}/steps/{step}", data=form)
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        tasks = client.get(f"/videos/{stem}/tasks").json()
        if tasks and tasks[-1]["status"] in ("done", "failed", "skipped"):
            return tasks[-1]
        time.sleep(0.05)
    raise AssertionError(f"task did not settle: {tasks}")


def _session_path(web_env: dict[str, Path], stem: str) -> Path:
    return web_env["output_dir"] / stem / paths.WEB_SESSION_FILE_NAME


def _read_session(web_env: dict[str, Path], stem: str) -> dict:
    return json.loads(_session_path(web_env, stem).read_text(encoding="utf-8"))


# --- 5. analyze prompt persisted before the skip check ---------------------


def test_analyze_prompt_is_persisted_even_when_step_skips(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)
    _run_step(client, stem, "extract-audio")
    _run_step(client, stem, "transcribe")
    _run_step(client, stem, "analyze", prompt="first prompt")
    web_env["calls_file"].unlink()

    task = _run_step(client, stem, "analyze", prompt="second prompt")

    assert task["status"] == "skipped"
    # 提交的新提示词虽未消费，仍须落到 session，预填反映最后一次提交。
    assert _read_session(web_env, stem)["analyze_prompt"] == "second prompt"
    response = client.get(f"/videos/{stem}")
    assert "second prompt" in response.text


# --- 6. force re-analyze resets the draft ----------------------------------


def _force_rerun_analyze(
    client: TestClient,
    web_env: dict[str, Path],
    stem: str,
    highlights: list[dict],
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    monkeypatch.setenv("VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps(highlights))
    return _run_step(client, stem, "analyze", force="true")


def test_force_reanalyze_resets_draft_from_new_highlights(
    client: TestClient,
    web_env: dict[str, Path],
    fixture_video: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stem = _register_video(client, fixture_video)
    _run_step(client, stem, "extract-audio")
    _run_step(client, stem, "transcribe")
    _run_step(client, stem, "analyze")
    # 编辑 draft：改边界锁定一项。
    response = client.post(
        f"/videos/{stem}/highlights/0/boundaries",
        data={"start": "2.6", "end": "4.9"},
    )
    assert response.status_code == 200

    _force_rerun_analyze(client, web_env, stem, CANNED_HIGHLIGHTS, monkeypatch)

    draft = json.loads(
        (web_env["output_dir"] / stem / paths.HIGHLIGHTS_DRAFT_FILE_NAME)
        .read_text(encoding="utf-8")
    )
    # draft 从新 highlights.json 重新生成：全部解锁，边界回到新文件值。
    assert [item["title"] for item in draft] == [
        item["title"] for item in CANNED_HIGHLIGHTS
    ]
    assert all(item["locked"] is False for item in draft)
    assert draft[0]["start"] == CANNED_HIGHLIGHTS[0]["start"]


def test_nonforced_analyze_skip_keeps_draft_untouched(
    client: TestClient,
    web_env: dict[str, Path],
    fixture_video: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stem = _register_video(client, fixture_video)
    _run_step(client, stem, "extract-audio")
    _run_step(client, stem, "transcribe")
    _run_step(client, stem, "analyze")
    client.post(
        f"/videos/{stem}/highlights/0/boundaries",
        data={"start": "2.6", "end": "4.9"},
    )
    draft_path = web_env["output_dir"] / stem / paths.HIGHLIGHTS_DRAFT_FILE_NAME
    before = draft_path.read_bytes()

    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE",
        json.dumps([CANNED_HIGHLIGHTS[0]]),
    )
    task = _run_step(client, stem, "analyze")

    assert task["status"] == "skipped"
    assert draft_path.read_bytes() == before


# --- 4. cut step card has no dead trigger form -----------------------------


def test_cut_card_has_no_trigger_form_but_shows_status(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    stem = _register_video(client, fixture_video)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    assert 'id="step-cut"' in html
    cut_card = html.split('id="step-cut"', 1)[1]
    assert f'action="/videos/{stem}/steps/cut"' not in cut_card


def test_step_trigger_forms_use_htmx_partial_swap(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    """触发步骤的表单必须走 HTMX 局部替换整条步骤条。

    回归：裸 form POST 让浏览器整页跳到 202 响应（一张裸步骤条片段），
    页面丢失 EventSource 接线，任务完成后状态永远卡在 running。
    """
    stem = _register_video(client, fixture_video)

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    for step in ("extract-audio", "transcribe", "analyze"):
        item = html.split(f'id="step-{step}"', 1)[1].split("</li>", 1)[0]
        assert f'hx-post="/videos/{stem}/steps/{step}"' in item, step
        assert 'hx-target="#steps"' in item, step
        assert 'hx-swap="outerHTML"' in item, step
        assert f'method="post" action="/videos/{stem}/steps/{step}"' not in item, step


def test_cut_forms_use_htmx_partial_swap(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    """最终剪切的三个表单同样走 HTMX：报告请求、直接切、报告内确认。

    与步骤触发表单同 bug 类：裸 POST 会把浏览器整页跳到 HTML 片段，
    丢掉 SSE 接线。
    """
    stem = _register_video(client, fixture_video)
    _run_step(client, stem, "extract-audio")
    _run_step(client, stem, "transcribe")
    _run_step(client, stem, "analyze")

    # 先出报告：独立报告片段（POST /cut 的响应）内的确认表单
    report_response = client.post(f"/videos/{stem}/cut")
    assert report_response.status_code == 200
    assert 'hx-post="/videos/' in report_response.text
    assert 'hx-target="#cut-report"' in report_response.text

    response = client.get(f"/videos/{stem}")

    assert response.status_code == 200
    html = response.text
    final_cut = html.split('id="final-cut"', 1)[1].split("</section>", 1)[0]
    assert f'hx-post="/videos/{stem}/cut"' in final_cut
    assert 'hx-target="#final-cut"' in final_cut
    # 详情页内嵌的报告确认表单（报告存 session 后随详情页渲染）
    report_section = html.split('id="cut-report"', 1)
    assert len(report_section) == 2
    assert 'hx-target="#cut-report"' in report_section[1]


def test_steps_cut_endpoint_is_not_wired(
    client: TestClient, web_env: dict[str, Path], fixture_video: Path
) -> None:
    """cut 不再走 /steps 触发端点：真正的剪切在 /cut 两段式入口。"""
    stem = _register_video(client, fixture_video)

    response = client.post(f"/videos/{stem}/steps/cut")

    assert response.status_code == 404


# --- 8. confirm uses the stored plan; stale report -> 409 -------------------

TRANSCRIPT = {
    "sentences": [
        {"begin_time": 1.0, "end_time": 3.0, "text": "大家好，欢迎来到本期视频。"},
        {"begin_time": 4.0, "end_time": 6.0, "text": "其实九成的人都搞错了。"},
        {"begin_time": 7.0, "end_time": 9.0, "text": "记得关注下期节目。"},
    ],
    "words": [],
}

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
def cut_studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """An app whose video has transcript + highlights + draft on disk."""
    monkeypatch.chdir(tmp_path)
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
def cut_client(cut_studio: dict, fixture_video: Path) -> TestClient:
    session_path = cut_studio["target_dir"] / paths.WEB_SESSION_FILE_NAME
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["source_path"] = str(fixture_video)
    session_path.write_text(json.dumps(session), encoding="utf-8")
    return TestClient(create_app(cut_studio["output_dir"]))


def test_boundary_edit_invalidates_report_and_confirm_returns_409(
    cut_client: TestClient, cut_studio: dict
) -> None:
    stem = cut_studio["stem"]
    response = cut_client.post(f"/videos/{stem}/cut")
    assert response.status_code == 200

    # 报告生成后只改边界（标题集合不变）——旧检查抓不到，新检查必须 409。
    response = cut_client.post(
        f"/videos/{stem}/highlights/0/boundaries",
        data={"start": "0.5", "end": "3.5"},
    )
    assert response.status_code == 200

    response = cut_client.post(f"/videos/{stem}/cut", data={"confirm": "true"})

    assert response.status_code == 409
    # 报告已失效并从 session 清除，不落任何切片产物。
    assert "cut_report" not in _session_dict(cut_studio)
    assert not (cut_studio["target_dir"] / paths.CLIPS_DIR_NAME).exists()


def test_delete_edit_invalidates_report_and_confirm_returns_409(
    cut_client: TestClient, cut_studio: dict
) -> None:
    stem = cut_studio["stem"]
    assert cut_client.post(f"/videos/{stem}/cut").status_code == 200

    assert cut_client.post(f"/videos/{stem}/highlights/1/delete").status_code == 200

    response = cut_client.post(f"/videos/{stem}/cut", data={"confirm": "true"})

    assert response.status_code == 409


def test_reorder_edit_invalidates_report_and_confirm_returns_409(
    cut_client: TestClient, cut_studio: dict
) -> None:
    stem = cut_studio["stem"]
    assert cut_client.post(f"/videos/{stem}/cut").status_code == 200

    response = cut_client.post(
        f"/videos/{stem}/highlights/reorder", data={"order": ["1", "0"]}
    )
    assert response.status_code == 200

    response = cut_client.post(f"/videos/{stem}/cut", data={"confirm": "true"})

    assert response.status_code == 409


def test_confirm_without_edits_executes_the_stored_plan(
    cut_client: TestClient, cut_studio: dict
) -> None:
    """无报告直接剪切（直接剪切合并按钮）仍现场规划并成功。"""
    stem = cut_studio["stem"]
    response = cut_client.post(f"/videos/{stem}/cut", data={"confirm": "true"})
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        tasks = cut_client.get(f"/videos/{stem}/tasks").json()
        if tasks and tasks[-1]["status"] in ("done", "failed", "skipped"):
            assert tasks[-1]["status"] == "done", tasks[-1]["error"]
            break
        time.sleep(0.05)
    else:
        raise AssertionError(f"task did not settle: {tasks}")
    assert (cut_studio["target_dir"] / paths.MERGED_FILE_NAME).exists()


def _session_dict(studio: dict) -> dict:
    session_path = studio["target_dir"] / paths.WEB_SESSION_FILE_NAME
    return json.loads(session_path.read_text(encoding="utf-8"))


# --- 7. SSE pending is broadcast -------------------------------------------


def test_pending_transition_is_broadcast_to_subscribers() -> None:
    runner = TaskRunner()
    subscriber_iter = runner.subscribe()
    queue = next(subscriber_iter)
    try:
        runner.try_start("stem", "extract-audio", lambda: "ok")
        first = queue.get(timeout=5)
        payload = json.loads(first.split("data: ", 1)[1])
        assert payload["status"] == "pending"
    finally:
        subscriber_iter.close()
    deadline = time.monotonic() + 5
    while runner.is_busy() and time.monotonic() < deadline:
        time.sleep(0.01)


# --- 9/10. TaskRunner.acquire signature + snapshot ---------------------------


def test_acquire_takes_no_arguments() -> None:
    runner = TaskRunner()
    runner.acquire()
    try:
        assert runner.is_busy()
    finally:
        runner.release()


def test_snapshot_returns_all_task_states() -> None:
    runner = TaskRunner()
    state = runner.try_start("stem", "analyze", lambda: "ok")
    deadline = time.monotonic() + 5
    while runner.is_busy() and time.monotonic() < deadline:
        time.sleep(0.01)

    snapshot = runner.snapshot()

    assert [s.task_id for s in snapshot] == [state.task_id]


# --- 11. WebSession dataclass ------------------------------------------------


def test_web_session_round_trip() -> None:
    session = WebSession(
        source_path="/videos/a.mp4",
        analyze_prompt="找反转",
        cut_report={"status": "pending", "items": []},
    )
    restored = WebSession.from_dict(session.to_dict())
    assert restored == session


def test_web_session_from_dict_defaults() -> None:
    session = WebSession.from_dict({"source_path": "/videos/a.mp4"})
    assert session.analyze_prompt == ""
    assert session.cut_report is None
