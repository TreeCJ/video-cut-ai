"""Web workbench per-video session state.

The session is a small JSON file (``web-session.json``) in the video's
output directory: the only mutable state the web layer keeps next to the
immutable pipeline artifacts. ``WebSession`` types its three fields;
serialization keeps the plain-dict JSON shape on disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from video_cut import paths


@dataclass(frozen=True)
class WebSession:
    """一个 output 子目录的 web 会话状态。"""

    source_path: str
    analyze_prompt: str = ""
    cut_report: dict[str, Any] | None = None
    # 报告生成时的 draft 指纹；任何 draft 编辑使其失效（确认时 409）。
    cut_report_fingerprint: tuple[tuple[str, float, float], ...] | None = field(
        default=None, compare=False
    )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"source_path": self.source_path}
        if self.analyze_prompt:
            data["analyze_prompt"] = self.analyze_prompt
        if self.cut_report is not None:
            data["cut_report"] = self.cut_report
        if self.cut_report_fingerprint is not None:
            data["cut_report_fingerprint"] = [
                [title, start, end]
                for title, start, end in self.cut_report_fingerprint
            ]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WebSession:
        raw_fingerprint = data.get("cut_report_fingerprint")
        fingerprint = (
            tuple((str(title), float(start), float(end)) for title, start, end in raw_fingerprint)
            if isinstance(raw_fingerprint, list)
            else None
        )
        cut_report = data.get("cut_report")
        return cls(
            source_path=str(data.get("source_path", "")),
            analyze_prompt=str(data.get("analyze_prompt", "")),
            cut_report=cut_report if isinstance(cut_report, dict) else None,
            cut_report_fingerprint=fingerprint,
        )


def load_session(target_dir: Path) -> WebSession | None:
    """读取一个 output 子目录的 session；缺失或损坏返回 None。"""
    session_path = target_dir / paths.WEB_SESSION_FILE_NAME
    if not session_path.exists():
        return None
    try:
        raw = json.loads(session_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    return WebSession.from_dict(raw)


def save_session(target_dir: Path, session: WebSession) -> None:
    """整体重写 session（小 JSON，单任务锁已覆盖并发）。"""
    session_path = target_dir / paths.WEB_SESSION_FILE_NAME
    session_path.write_text(
        json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
