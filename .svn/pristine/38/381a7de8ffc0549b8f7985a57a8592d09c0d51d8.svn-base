"""Draft editing endpoints for the web workbench.

Each edit endpoint rewrites the whole draft file and re-renders the card
list (HTMX swap target). All edits go through ``save_draft``; the original
highlights.json is never touched. Writes are serialized with a lock — the
single-task lock only guards pipeline tasks, draft edits are lightweight
synchronous writes.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from video_cut import paths
from video_cut.audio import probe_duration
from video_cut.web.draft import DraftHighlight, load_or_create_draft, save_draft
from video_cut.web.session import load_session
from video_cut.web.steps import ANALYZE_DURATION_BUDGET_SECONDS


def slider_max(
    video_duration: float | None, draft: list[DraftHighlight]
) -> float:
    """滑杆统一刻度的 max：视频总长；未知时回退到高光最大边界 + 预算余量。

    统一 [0, max] 刻度让两滑块屏幕位置等于真实时间轴位置（左边必是 IN）。
    """
    if video_duration:
        return video_duration
    fallback = max((h.end for h in draft), default=0.0)
    return fallback + ANALYZE_DURATION_BUDGET_SECONDS


def _render_cards(
    request: Request,
    templates: Jinja2Templates,
    stem: str,
    draft: list[DraftHighlight],
    video_duration: float | None = None,
) -> HTMLResponse:
    """编辑端点的统一响应：整段卡片列表重渲染（HTMX swap 目标）。"""
    return templates.TemplateResponse(
        request,
        "highlight_cards.html",
        {
            "stem": stem,
            "highlights": draft,
            "total_duration": sum(h.duration for h in draft),
            "duration_budget": ANALYZE_DURATION_BUDGET_SECONDS,
            "video_duration": video_duration,
            "slider_max": slider_max(video_duration, draft),
        },
    )


def _load_draft_for_edit(
    output_dir: Path, stem: str
) -> tuple[Path, list[DraftHighlight]] | HTMLResponse:
    """编辑前置校验：视频存在且已有 highlights/draft 可供编辑。"""
    target_dir = output_dir / stem
    if load_session(target_dir) is None:
        return HTMLResponse(f"未知视频: {stem}", status_code=404)
    if not (target_dir / paths.HIGHLIGHTS_FILE_NAME).exists() and not (
        target_dir / paths.HIGHLIGHTS_DRAFT_FILE_NAME
    ).exists():
        return HTMLResponse("尚无高光可编辑：先运行 analyze", status_code=409)
    return target_dir, load_or_create_draft(target_dir)


def _load_video_duration(target_dir: Path) -> float | None:
    """编辑响应重渲染卡片时沿用视频总长（滑杆刻度不漂移）。"""
    session = load_session(target_dir)
    if session is None:
        return None
    source = Path(session.source_path)
    return probe_duration(source) if source.is_file() else None


def register_edit_routes(
    app: FastAPI,
    templates: Jinja2Templates,
    output_dir: Path,
    draft_lock: threading.Lock,
) -> None:
    """注册 draft 编辑路由（边界 / 删除 / 重排）。"""
    _register_item_edit_routes(app, templates, output_dir, draft_lock)
    _register_reorder_route(app, templates, output_dir, draft_lock)


def _register_item_edit_routes(
    app: FastAPI,
    templates: Jinja2Templates,
    output_dir: Path,
    draft_lock: threading.Lock,
) -> None:
    """单卡编辑路由：边界修改与删除。"""

    @app.post("/videos/{stem}/highlights/{index}/boundaries", response_model=None)
    def update_boundaries(
        request: Request,
        stem: str,
        index: int,
        start: float = Form(...),
        end: float = Form(...),
    ) -> HTMLResponse:
        """手动改边界：更新 draft，该项 locked=true，其他项不受影响。"""
        loaded = _load_draft_for_edit(output_dir, stem)
        if isinstance(loaded, HTMLResponse):
            return loaded
        target_dir, draft = loaded
        if not 0 <= index < len(draft):
            return HTMLResponse(f"未知 Highlight 序号: {index}", status_code=404)
        if end <= start:
            return HTMLResponse("end 必须大于 start", status_code=422)
        with draft_lock:
            updated = list(draft)
            updated[index] = replace(
                updated[index], start=start, end=end, locked=True
            )
            save_draft(target_dir, updated)
        return _render_cards(
            request, templates, stem, updated, _load_video_duration(target_dir)
        )

    @app.post("/videos/{stem}/highlights/{index}/delete", response_model=None)
    def delete_highlight(request: Request, stem: str, index: int) -> HTMLResponse:
        """删除一张卡片：从 draft 移除，不影响其他项的 locked。"""
        loaded = _load_draft_for_edit(output_dir, stem)
        if isinstance(loaded, HTMLResponse):
            return loaded
        target_dir, draft = loaded
        if not 0 <= index < len(draft):
            return HTMLResponse(f"未知 Highlight 序号: {index}", status_code=404)
        with draft_lock:
            updated = [h for i, h in enumerate(draft) if i != index]
            save_draft(target_dir, updated)
        return _render_cards(
            request, templates, stem, updated, _load_video_duration(target_dir)
        )


def _register_reorder_route(
    app: FastAPI,
    templates: Jinja2Templates,
    output_dir: Path,
    draft_lock: threading.Lock,
) -> None:
    """整列重排路由。"""

    @app.post("/videos/{stem}/highlights/reorder", response_model=None)
    def reorder_highlights(
        request: Request, stem: str, order: list[str] = Form(...)
    ) -> HTMLResponse:
        """拖拽重排：order 是原序号的新排列，必须是完整置换。"""
        loaded = _load_draft_for_edit(output_dir, stem)
        if isinstance(loaded, HTMLResponse):
            return loaded
        target_dir, draft = loaded
        try:
            permutation = [int(value) for value in order]
        except ValueError:
            return HTMLResponse("order 必须是整数序号列表", status_code=422)
        if sorted(permutation) != list(range(len(draft))):
            return HTMLResponse(
                "order 必须是全部 Highlight 序号的完整排列", status_code=422
            )
        with draft_lock:
            updated = [draft[i] for i in permutation]
            save_draft(target_dir, updated)
        return _render_cards(
            request, templates, stem, updated, _load_video_duration(target_dir)
        )
