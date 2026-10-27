"""FastAPI app factory for the video-cut web workbench.

App factory pattern: tests build the app with a custom output dir via
``create_app(output_dir)``; the ``serve`` CLI command uses the default.
Route registrations live here; step machinery in ``web.steps``, the final
cut flow in ``web.cut``, draft editing in ``web.editing``, session state in
``web.session``.
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request, UploadFile
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from video_cut import paths
from video_cut.asr import read_transcript
from video_cut.audio import probe_duration
from video_cut.web.auth import router as auth_router, register_auth_routes
from video_cut.web.clip_management import router as clip_router
from video_cut.web.settings import router as settings_router
from video_cut.web.cut import register_cut_artifact_routes, register_cut_routes
from video_cut.web.upload import (
    get_upload_dir,
    save_uploaded_file,
    validate_upload_file,
)
from video_cut.web.draft import DraftHighlight, load_or_create_draft
from video_cut.web.editing import register_edit_routes, slider_max
from video_cut.web.session import WebSession, load_session, save_session
from video_cut.web.steps import (
    ANALYZE_DURATION_BUDGET_SECONDS,
    STEP_NAMES,
    STEP_REGISTRY,
    StepContext,
    build_run_to_highlights_work,
)
from video_cut.web.tasks import TaskBusyError, TaskRunner

_PACKAGE_DIR = Path(__file__).parent

DEFAULT_PORT = 8462


# Paths that don't require authentication
PUBLIC_PATHS = [
    "/login",
    "/register",
    "/static",
    "/output",
    "/docs",
    "/openapi.json",
    "/auth/login",
    "/auth/register",
    "/api/settings",  # Settings API is protected but page needs auth
]


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to check if user is authenticated before accessing protected routes."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if any(path.startswith(public_path) for public_path in PUBLIC_PATHS):
            return await call_next(request)

        # Check if user is authenticated (from cookie or Authorization header)
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # Debug logging
        print(f"[AuthMiddleware] Path: {path}, Token from cookie: {bool(request.cookies.get('access_token'))}, Token from header: {bool(token)}")

        # If no token found, handle based on request type
        if not token:
            if path.startswith("/api/"):
                # For API endpoints, return 401
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Not authenticated. Please log in first."}
                )
            else:
                # For page requests, redirect to login
                return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)


@dataclass(frozen=True)
class LibraryEntry:
    """首页视频库条目：一个 output 子目录及其源文件可用性。"""

    stem: str
    source_path: str
    source_exists: bool


@dataclass(frozen=True)
class StepStatus:
    """详情页一个流水线步骤卡片的状态（产物存在性 + 最近一次任务结果）。"""

    name: str
    status: str  # pending | running | done | failed | skipped
    detail: str = ""
    error: str = ""


def _scan_library(output_dir: Path) -> list[LibraryEntry]:
    """扫 output 目录：有 session 的目录列出，源文件消失的灰显。"""
    entries: list[LibraryEntry] = []
    if not output_dir.exists():
        return entries
    for child in sorted(output_dir.iterdir()):
        if not child.is_dir():
            continue
        session = load_session(child)
        if session is None:
            continue
        entries.append(
            LibraryEntry(
                stem=child.name,
                source_path=session.source_path,
                source_exists=Path(session.source_path).is_file(),
            )
        )
    return entries


def _step_statuses(
    target_dir: Path, runner: TaskRunner, stem: str
) -> list[StepStatus]:
    """步骤状态 = 产物存在性，叠加最近一次任务结果（failed/skipped 优先展示）。

    combo 任务（run-to-highlights）失败时，其 step 名不匹配任何单步，
    需把错误挂到第一个未完成步骤上——即 combo 停下的那一环。
    若所有步骤均已完成（异常边缘），挂到 analyze。
    """
    latest = runner.latest_for_stem(stem)
    statuses: list[StepStatus] = []
    # 预计算 combo 失败要挂到哪一步
    combo_error_step: str | None = None
    if (
        latest is not None
        and latest.step == "run-to-highlights"
        and latest.status == "failed"
    ):
        for name in STEP_NAMES:
            if not STEP_REGISTRY[name].artifact_done(target_dir):
                combo_error_step = name
                break
        else:
            combo_error_step = "analyze"

    for name in STEP_NAMES:
        status = (
            "done"
            if STEP_REGISTRY[name].artifact_done(target_dir)
            else "pending"
        )
        detail = ""
        error = ""
        if latest is not None and latest.step == name:
            if latest.status == "running":
                status = "running"
            elif latest.status == "failed":
                status = "failed"
                error = latest.error
            elif latest.status == "skipped":
                detail = latest.detail
        elif name == combo_error_step:
            status = "failed"
            error = latest.error
        statuses.append(
            StepStatus(name=name, status=status, detail=detail, error=error)
        )
    return statuses


def _detail_context(
    target_dir: Path, session: WebSession, runner: TaskRunner, stem: str
) -> dict:
    """详情页模板上下文：步骤状态 + 转录 + draft + 切片产物 + 视频时长。"""
    transcript_path = target_dir / paths.TRANSCRIPT_FILE_NAME
    sentences = (
        read_transcript(transcript_path).sentences
        if transcript_path.exists()
        else ()
    )
    highlights: list[DraftHighlight] = []
    if (target_dir / paths.HIGHLIGHTS_FILE_NAME).exists() or (
        target_dir / paths.HIGHLIGHTS_DRAFT_FILE_NAME
    ).exists():
        # Draft 存在则读 Draft；否则首次打开时从 highlights.json 生成。
        highlights = load_or_create_draft(target_dir)
    clips_dir = target_dir / paths.CLIPS_DIR_NAME
    clips = (
        sorted(p.name for p in clips_dir.glob("*.mp4"))
        if clips_dir.exists()
        else []
    )
    source = Path(session.source_path)
    video_duration = probe_duration(source) if source.is_file() else None
    return {
        "stem": stem,
        "source_path": session.source_path,
        "steps": _step_statuses(target_dir, runner, stem),
        "sentences": sentences,
        "source_available": source.is_file(),
        "video_duration": video_duration,
        "analyze_prompt": session.analyze_prompt,
        "task_running": runner.is_busy(),
        "highlights": highlights,
        "total_duration": sum(h.duration for h in highlights),
        "duration_budget": ANALYZE_DURATION_BUDGET_SECONDS,
        "cut_report": session.cut_report,
        "clips": clips,
        "merged_available": (target_dir / paths.MERGED_FILE_NAME).is_file(),
        "slider_max": slider_max(video_duration, highlights),
    }


def _render_step_strip(
    request: Request,
    templates: Jinja2Templates,
    stem: str,
    steps: list[StepStatus],
    analyze_prompt: str,
    task_running: bool,
) -> str:
    """渲染整条步骤条（触发端点的 202 响应体与 detail 页共用）。"""
    template = templates.get_template("step_strip.html")
    return template.render(
        request=request,
        stem=stem,
        steps=steps,
        analyze_prompt=analyze_prompt,
        task_running=task_running,
    )


def _register_library_routes(
    app: FastAPI, templates: Jinja2Templates, output_dir: Path
) -> None:
    """首页与新建工作流路由。"""

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        entries = _scan_library(output_dir)
        return templates.TemplateResponse(
            request, "home.html", {"entries": entries}
        )

    @app.post("/videos", response_model=None)
    async def create_workflow(
        request: Request,
        video_file: Optional[UploadFile] = None,
        video_path: str = Form(None),
    ) -> RedirectResponse | HTMLResponse:
        """Create workflow from uploaded file or local path.

        Priority: uploaded file > local path
        """
        source_path = None

        # Handle file upload
        if video_file and video_file.filename:
            try:
                upload_dir = get_upload_dir(output_dir)
                saved_path, file_size = await save_uploaded_file(
                    upload_dir, video_file
                )
                source_path = str(saved_path)
            except ValueError as error:
                entries = _scan_library(output_dir)
                return templates.TemplateResponse(
                    request,
                    "home.html",
                    {
                        "entries": entries,
                        "error": str(error),
                    },
                    status_code=422,
                )
        # Fallback to local path (for backward compatibility)
        elif video_path:
            source = Path(video_path)
            if not source.is_absolute() or not source.is_file():
                entries = _scan_library(output_dir)
                return templates.TemplateResponse(
                    request,
                    "home.html",
                    {
                        "entries": entries,
                        "error": f"视频文件不存在或不是文件: {video_path}",
                    },
                    status_code=422,
                )
            source_path = str(source)
        else:
            entries = _scan_library(output_dir)
            return templates.TemplateResponse(
                request,
                "home.html",
                {
                    "entries": entries,
                    "error": "请上传视频文件或提供本地路径",
                },
                status_code=422,
            )

        # Create workflow
        source = Path(source_path)
        target_dir = output_dir / source.stem
        target_dir.mkdir(parents=True, exist_ok=True)
        save_session(target_dir, WebSession(source_path=str(source)))
        return RedirectResponse(f"/videos/{source.stem}", status_code=303)


def _register_video_routes(
    app: FastAPI,
    templates: Jinja2Templates,
    output_dir: Path,
    runner: TaskRunner,
) -> None:
    """详情页、源视频流、步骤触发、任务观测路由。"""
    _register_detail_routes(app, templates, output_dir, runner)
    _register_step_trigger_route(app, templates, output_dir, runner)

    @app.post("/videos/{stem}/analyze", response_model=None)
    def analyze_from_prompt(
        request: Request,
        stem: str,
        prompt: str = Form(""),
        force: bool = Form(False),
    ) -> HTMLResponse:
        """第一幕「生成高光」：带提示词跑 analyze。

        transcript 缺失时自动先跑 run-to-highlights（抽音 → 转录 → 选题
        一气呵成）；已有 transcript 则只跑 analyze。force 透传给步骤
        （强制重跑会刷新 highlights.json 并重置 draft）。
        """
        target_dir = output_dir / stem
        session = load_session(target_dir)
        if session is None:
            return HTMLResponse(f"未知视频: {stem}", status_code=404)
        has_transcript = (target_dir / paths.TRANSCRIPT_FILE_NAME).exists()
        # transcript 存在时恒走单步 analyze（force 透传给步骤：force 重跑
        # 只刷新 highlights，不重建上游抽音/转录）。force=true 也不例外：
        # 组合任务内部 force 固定 False，上游永远 skip，analyze 也会跟着
        # skip——等于什么都没重跑。
        if has_transcript:
            step = "analyze"
            definition = STEP_REGISTRY[step]
            context = StepContext(
                output_dir=output_dir,
                stem=stem,
                source_path=session.source_path,
                force=force,
                prompt=prompt,
            )
            work = definition.build_work(context)
        else:
            # 无 transcript：组合任务补齐前置步骤（内部各步自带 skip）。
            step = "run-to-highlights"
            context = StepContext(
                output_dir=output_dir,
                stem=stem,
                source_path=session.source_path,
                force=False,  # 组合任务自身管理各步 skip 语义
                prompt=prompt,
            )
            work = build_run_to_highlights_work(context)
        try:
            state = runner.try_start(stem, step, work)
        except TaskBusyError:
            return HTMLResponse("已有任务在运行，请等待完成", status_code=409)
        steps = _step_statuses(target_dir, runner, stem)
        # 触发端点的即时响应强制把相关步标为 running。
        steps = [
            StepStatus(name=s.name, status="running")
            if s.name in ("analyze", "transcribe", "extract-audio")
            and (step == "run-to-highlights" or s.name == "analyze")
            else s
            for s in steps
        ]
        return HTMLResponse(
            _render_step_strip(
                request,
                templates,
                stem,
                steps,
                session.analyze_prompt,
                task_running=True,
            ),
            status_code=202,
        )

    @app.post("/videos/{stem}/run-to-highlights", response_model=None)
    def run_to_highlights(request: Request, stem: str) -> HTMLResponse:
        """一键跑到 highlights；任务锁被占用时返回 409。"""
        target_dir = output_dir / stem
        session = load_session(target_dir)
        if session is None:
            return HTMLResponse(f"未知视频: {stem}", status_code=404)
        context = StepContext(
            output_dir=output_dir,
            stem=stem,
            source_path=session.source_path,
            force=False,
            prompt="",
        )
        work = build_run_to_highlights_work(context)
        try:
            runner.try_start(stem, "run-to-highlights", work)
        except TaskBusyError:
            return HTMLResponse(
                "已有任务在运行，请等待完成", status_code=409
            )
        return HTMLResponse(
            _render_step_strip(
                request,
                templates,
                stem,
                _step_statuses(target_dir, runner, stem),
                session.analyze_prompt,
                task_running=True,
            ),
            status_code=202,
        )

    @app.get("/videos/{stem}/tasks")
    def list_tasks(stem: str) -> list[dict]:
        """某个视频的任务状态列表（测试与调试观测点）。"""
        return [
            {
                "task_id": s.task_id,
                "step": s.step,
                "status": s.status,
                "detail": s.detail,
                "error": s.error,
            }
            for s in runner.tasks_for_stem(stem)
        ]


def _register_detail_routes(
    app: FastAPI,
    templates: Jinja2Templates,
    output_dir: Path,
    runner: TaskRunner,
) -> None:
    """详情页与源视频流路由。"""

    @app.get("/videos/{stem}", response_class=HTMLResponse)
    def video_detail(request: Request, stem: str) -> HTMLResponse:
        target_dir = output_dir / stem
        session = load_session(target_dir)
        if session is None:
            return HTMLResponse(f"未知视频: {stem}", status_code=404)
        return templates.TemplateResponse(
            request,
            "detail.html",
            _detail_context(target_dir, session, runner, stem),
        )

    @app.get("/videos/{stem}/source", response_model=None)
    def source_video(stem: str) -> FileResponse | HTMLResponse:
        """源视频流式端点：FileResponse 自带 HTTP Range 支持（206）。"""
        target_dir = output_dir / stem
        session = load_session(target_dir)
        if session is None:
            return HTMLResponse(f"未知视频: {stem}", status_code=404)
        source = Path(session.source_path)
        if not source.is_file():
            return HTMLResponse(f"源视频不存在: {source}", status_code=404)
        return FileResponse(source)


def _register_step_trigger_route(
    app: FastAPI,
    templates: Jinja2Templates,
    output_dir: Path,
    runner: TaskRunner,
) -> None:
    """步骤触发路由：work 函数来自步骤注册表。"""

    @app.post("/videos/{stem}/steps/{step}", response_model=None)
    def trigger_step(
        request: Request,
        stem: str,
        step: str,
        force: bool = Form(False),
        prompt: str = Form(""),
    ) -> HTMLResponse:
        """触发一个流水线步骤；任务锁被占用时返回 409。"""
        target_dir = output_dir / stem
        session = load_session(target_dir)
        if session is None:
            return HTMLResponse(f"未知视频: {stem}", status_code=404)
        definition = STEP_REGISTRY.get(step)
        if definition is None:
            return HTMLResponse(f"未知步骤: {step}", status_code=404)
        context = StepContext(
            output_dir=output_dir,
            stem=stem,
            source_path=session.source_path,
            force=force,
            prompt=prompt,
        )
        try:
            work = definition.build_work(context)
        except ValueError as error:
            return HTMLResponse(str(error), status_code=404)
        try:
            state = runner.try_start(stem, step, work)
        except TaskBusyError:
            return HTMLResponse("已有任务在运行，请等待完成", status_code=409)
        steps = _step_statuses(target_dir, runner, stem)
        # 触发端点的即时响应强制把该步标为 running，即使任务线程尚未被观测到。
        steps = [
            StepStatus(name=s.name, status="running")
            if s.name == state.step
            else s
            for s in steps
        ]
        return HTMLResponse(
            _render_step_strip(
                request,
                templates,
                stem,
                steps,
                session.analyze_prompt,
                task_running=True,
            ),
            status_code=202,
        )


def _register_event_routes(app: FastAPI, runner: TaskRunner) -> None:
    """SSE 事件流路由。"""

    @app.get("/events")
    def events() -> StreamingResponse:
        """SSE：先推一次快照，之后实时推送任务状态迁移。"""

        def stream() -> Iterator[str]:
            snapshot = [
                {
                    "task_id": s.task_id,
                    "stem": s.stem,
                    "step": s.step,
                    "status": s.status,
                    "detail": s.detail,
                    "error": s.error,
                }
                for s in runner.snapshot()
            ]
            yield (
                "event: snapshot\n"
                f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
            )
            for subscriber in runner.subscribe():
                while True:
                    message = subscriber.get()
                    if message is None:
                        return
                    yield message

        return StreamingResponse(stream(), media_type="text/event-stream")


def create_app(output_dir: Path = Path("output")) -> FastAPI:
    """Build the FastAPI app bound to an output directory."""
    app = FastAPI(title="video-cut")
    
    # Add authentication middleware
    app.add_middleware(AuthMiddleware)
    
    templates = Jinja2Templates(directory=_PACKAGE_DIR / "templates")
    app.mount(
        "/static",
        StaticFiles(directory=_PACKAGE_DIR / "static"),
        name="static",
    )
    # Mount output directory for serving generated videos
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/output",
        StaticFiles(directory=str(output_dir)),
        name="output",
    )
    runner = TaskRunner()
    app.state.task_runner = runner
    # 编辑端点的写文件互斥：单任务锁只挡流水线任务，draft 编辑是轻量同步写。
    draft_lock = threading.Lock()

    # Register authentication routes
    app.include_router(auth_router)
    register_auth_routes(app, templates)

    # Register settings routes
    app.include_router(settings_router)

    # Register clip management routes
    app.include_router(clip_router)

    _register_library_routes(app, templates, output_dir)
    _register_video_routes(app, templates, output_dir, runner)
    _register_event_routes(app, runner)
    register_cut_routes(app, templates, output_dir, runner)
    register_cut_artifact_routes(app, output_dir)
    register_edit_routes(app, templates, output_dir, draft_lock)

    return app


def create_app_dev() -> FastAPI:
    """Reload 模式的 app 工厂：uvicorn --reload 需要 import 字符串入口。

    固定用 ``output`` 相对目录（与 CLI 默认一致，从工作目录解析）。
    """
    return create_app(Path("output"))

