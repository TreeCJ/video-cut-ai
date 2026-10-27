"""Final-cut planning and confirm handlers for the web workbench.

Two-phase flow: 生成对齐报告 stores an AlignmentReport (plus the draft
fingerprint it was planned from) in the session; 确认剪切合并 executes the
STORED plan — any draft edit after the report invalidates it and confirm
returns 409. The 直接剪切合并 path (no stored report) still plans live.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from video_cut import paths
from video_cut.align import align_highlights
from video_cut.asr import read_transcript
from video_cut.cutting import Highlight
from video_cut.web.draft import DraftHighlight, load_or_create_draft
from video_cut.web.session import WebSession, load_session, save_session
from video_cut.web.steps import cut_highlights_work
from video_cut.web.tasks import TaskBusyError, TaskRunner


@dataclass(frozen=True)
class AlignmentReportItem:
    """对齐报告的一条：一个 Highlight 从原始边界到最终边界的去向。"""

    title: str
    locked: bool
    original_start: float
    original_end: float
    final_start: float
    final_end: float
    moved: bool
    warning: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "locked": self.locked,
            "original_start": self.original_start,
            "original_end": self.original_end,
            "final_start": self.final_start,
            "final_end": self.final_end,
            "moved": self.moved,
            "warning": self.warning,
        }


@dataclass(frozen=True)
class AlignmentReport:
    """一次最终剪切的对齐计划：分流后的最终 Highlight 列表 + 逐项报告。"""

    items: tuple[AlignmentReportItem, ...]
    final_highlights: tuple[Highlight, ...]

    def to_dict(self) -> dict:
        return {
            "status": "pending",
            "items": [item.to_dict() for item in self.items],
            "final_highlights": [
                {
                    "title": h.title,
                    "reason": h.reason,
                    "quote": h.quote,
                    "start": h.start,
                    "end": h.end,
                }
                for h in self.final_highlights
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> AlignmentReport:
        """从 session 里存储的报告恢复执行计划（确认剪切的事实来源）。"""
        final_highlights = tuple(
            Highlight.from_dict(item, "stored cut report entry")
            for item in data["final_highlights"]
        )
        items = tuple(
            AlignmentReportItem(
                title=item["title"],
                locked=item["locked"],
                original_start=item["original_start"],
                original_end=item["original_end"],
                final_start=item["final_start"],
                final_end=item["final_end"],
                moved=item["moved"],
                warning=item.get("warning", ""),
            )
            for item in data["items"]
        )
        return cls(items=items, final_highlights=final_highlights)


def _draft_fingerprint(draft: list[DraftHighlight]) -> tuple[tuple[str, float, float], ...]:
    """Draft 的内容指纹：标题 + 边界；任何编辑（边界/删除/重排）都会改变它。"""
    return tuple((h.title, h.start, h.end) for h in draft)


def _align_unlocked(
    target_dir: Path,
    draft: list[DraftHighlight],
    unlocked_indices: list[int],
) -> dict[int, tuple[Highlight, str]]:
    """未锁定项过 quote 对齐；warning 按标题匹配回报告。"""
    transcript_path = target_dir / paths.TRANSCRIPT_FILE_NAME
    if not unlocked_indices or not transcript_path.exists():
        return {}
    unlocked = [
        Highlight(
            title=draft[i].title,
            reason=draft[i].reason,
            quote=draft[i].quote,
            start=draft[i].start,
            end=draft[i].end,
        )
        for i in unlocked_indices
    ]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        results = align_highlights(unlocked, read_transcript(transcript_path))
    # align 对每个未锁定项至多产生一条 warning；按标题匹配回报告。
    warnings_by_title: dict[str, str] = {}
    for warning in caught:
        message = str(warning.message)
        for highlight in unlocked:
            if repr(highlight.title) in message:
                warnings_by_title[highlight.title] = message
    return {
        index: (result, warnings_by_title.get(result.title, ""))
        for index, result in zip(unlocked_indices, results)
    }


def plan_final_cut(target_dir: Path) -> AlignmentReport:
    """Build the alignment plan for the final cut.

    Loads the Draft (falling back to highlights.json when no draft exists),
    splits items: locked highlights pass through verbatim; unlocked ones go
    through quote alignment against transcript.json (when it exists), with
    warnings captured into per-item report entries. Pipeline semantics match
    the CLI's cut command — only the locked split is added on top.
    """
    draft = load_or_create_draft(target_dir)
    unlocked_indices = [i for i, h in enumerate(draft) if not h.locked]
    aligned = _align_unlocked(target_dir, draft, unlocked_indices)

    items: list[AlignmentReportItem] = []
    final: list[Highlight] = []
    for index, entry in enumerate(draft):
        if index in aligned:
            final_highlight, warning = aligned[index]
        else:
            final_highlight = Highlight(
                title=entry.title,
                reason=entry.reason,
                quote=entry.quote,
                start=entry.start,
                end=entry.end,
            )
            warning = ""
        final.append(final_highlight)
        moved = (
            final_highlight.start != entry.start
            or final_highlight.end != entry.end
        )
        items.append(
            AlignmentReportItem(
                title=entry.title,
                locked=entry.locked,
                original_start=entry.start,
                original_end=entry.end,
                final_start=final_highlight.start,
                final_end=final_highlight.end,
                moved=moved,
                warning=warning,
            )
        )
    return AlignmentReport(items=tuple(items), final_highlights=tuple(final))


def _load_editable(
    output_dir: Path, stem: str
) -> tuple[Path, WebSession] | HTMLResponse:
    """cut 前置校验：视频存在且已有 highlights/draft 可供剪切。"""
    target_dir = output_dir / stem
    session = load_session(target_dir)
    if session is None:
        return HTMLResponse(f"未知视频: {stem}", status_code=404)
    if not (target_dir / paths.HIGHLIGHTS_FILE_NAME).exists() and not (
        target_dir / paths.HIGHLIGHTS_DRAFT_FILE_NAME
    ).exists():
        return HTMLResponse("尚无高光可剪切：先运行 analyze", status_code=409)
    return target_dir, session


def _request_report(
    request: Request,
    templates: Jinja2Templates,
    target_dir: Path,
    session: WebSession,
    stem: str,
) -> HTMLResponse:
    """第一阶段：只做分流与对齐，报告 + draft 指纹存 session，不落产物。"""
    try:
        report = plan_final_cut(target_dir)
    except ValueError as error:
        return HTMLResponse(str(error), status_code=422)
    save_session(
        target_dir,
        WebSession(
            source_path=session.source_path,
            analyze_prompt=session.analyze_prompt,
            cut_report=report.to_dict(),
            cut_report_fingerprint=_draft_fingerprint(
                load_or_create_draft(target_dir)
            ),
        ),
    )
    return templates.TemplateResponse(
        request, "cut_report.html", {"stem": stem, "report": report}
    )


def _resolve_confirm_plan(
    target_dir: Path, session: WebSession
) -> list[Highlight] | HTMLResponse:
    """确认时的计划来源：存储的报告（指纹校验）或现场规划（直接剪切）。"""
    if session.cut_report is None:
        try:
            return list(plan_final_cut(target_dir).final_highlights)
        except ValueError as error:
            return HTMLResponse(str(error), status_code=422)
    current = _draft_fingerprint(load_or_create_draft(target_dir))
    if session.cut_report_fingerprint != current:
        # 报告过期：草稿在出报告后被改过，清除报告，要求重新确认。
        save_session(
            target_dir,
            WebSession(
                source_path=session.source_path,
                analyze_prompt=session.analyze_prompt,
            ),
        )
        return HTMLResponse(
            "草稿已变化，请重新确认对齐报告", status_code=409
        )
    stored = AlignmentReport.from_dict(session.cut_report)
    return list(stored.final_highlights)


def _confirm_cut(
    request: Request,
    templates: Jinja2Templates,
    output_dir: Path,
    runner: TaskRunner,
    stem: str,
    target_dir: Path,
    session: WebSession,
    subtitles: bool = False,
) -> HTMLResponse:
    """第二阶段：执行存储的计划（无报告则现场规划），经任务锁跑重活。"""
    planned = _resolve_confirm_plan(target_dir, session)
    if isinstance(planned, HTMLResponse):
        return planned
    source = Path(session.source_path)
    if not source.is_file():
        return HTMLResponse(f"源视频不存在: {source}", status_code=409)

    work = cut_highlights_work(output_dir, stem, source, planned, subtitles=subtitles)
    try:
        runner.try_start(stem, "cut", work)
    except TaskBusyError:
        return HTMLResponse("已有任务在运行，请等待完成", status_code=409)
    # 任务已受理：清除待确认报告。
    save_session(
        target_dir,
        WebSession(
            source_path=session.source_path,
            analyze_prompt=session.analyze_prompt,
        ),
    )
    # 片段根 id 是 cut-progress，与详情页的 #final-cut 区不撞 id：
    # outerHTML 替换原 target 后页面上只保留这一个进度段。
    return templates.TemplateResponse(
        request, "cut_progress.html", {}, status_code=202
    )


def register_cut_routes(
    app: FastAPI,
    templates: Jinja2Templates,
    output_dir: Path,
    runner: TaskRunner,
) -> None:
    """注册最终剪切的两段式入口路由。"""

    @app.post("/videos/{stem}/cut", response_model=None)
    def trigger_cut(
        request: Request, 
        stem: str, 
        confirm: bool = Form(False),
        subtitles: bool = Form(False),
    ) -> HTMLResponse:
        """最终剪切的两阶段入口（详见模块 docstring）。"""
        loaded = _load_editable(output_dir, stem)
        if isinstance(loaded, HTMLResponse):
            return loaded
        target_dir, session = loaded
        if not confirm:
            return _request_report(request, templates, target_dir, session, stem)
        return _confirm_cut(
            request, templates, output_dir, runner, stem, target_dir, session, subtitles
        )


def register_cut_artifact_routes(app: FastAPI, output_dir: Path) -> None:
    """注册对齐报告与切片产物的观测端点。"""

    @app.get("/videos/{stem}/cut/report", response_model=None)
    def cut_report(stem: str) -> dict | HTMLResponse:
        """最近一次请求的待确认对齐报告（观测点 + 前端轮询用）。"""
        target_dir = output_dir / stem
        session = load_session(target_dir)
        if session is None:
            return HTMLResponse(f"未知视频: {stem}", status_code=404)
        report = session.cut_report
        if report is None:
            return HTMLResponse("尚无待确认的对齐报告", status_code=404)
        # 报告详情只回传逐项条目，执行计划字段属内部状态。
        return {"status": report["status"], "items": report["items"]}

    @app.get("/videos/{stem}/clips/{filename}", response_model=None)
    def serve_clip(stem: str, filename: str) -> FileResponse | HTMLResponse:
        """切片产物静态端点；文件名必须落在 clips 目录内。"""
        target_dir = output_dir / stem
        if load_session(target_dir) is None:
            return HTMLResponse(f"未知视频: {stem}", status_code=404)
        clips_dir = (target_dir / paths.CLIPS_DIR_NAME).resolve()
        clip_path = (clips_dir / filename).resolve()
        if clip_path.parent != clips_dir or not clip_path.is_file():
            return HTMLResponse(f"未知切片: {filename}", status_code=404)
        return FileResponse(clip_path, media_type="video/mp4")

    @app.get("/videos/{stem}/merged", response_model=None)
    def serve_merged(stem: str) -> FileResponse | HTMLResponse:
        target_dir = output_dir / stem
        if load_session(target_dir) is None:
            return HTMLResponse(f"未知视频: {stem}", status_code=404)
        merged_path = target_dir / paths.MERGED_FILE_NAME
        if not merged_path.is_file():
            return HTMLResponse("尚无 merged.mp4", status_code=404)
        return FileResponse(merged_path, media_type="video/mp4")
