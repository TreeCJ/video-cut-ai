"""Pipeline step registry for the web workbench.

Single source of truth for the four pipeline steps: each entry maps a step
name to its artifact check (skip 判断与 CLI 同一套：按产物存在性) and its
work function factory. Adding a step = one registry entry. Work functions
reuse the pipeline modules and CLI builders so web semantics match the CLI.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from video_cut import paths
from video_cut.asr import read_transcript
from video_cut.audio import extract_audio
from video_cut.config import ASR_CONFIG_KEYS_REQUIRED, LLM_CONFIG_KEYS, require_config
from video_cut.cutting import Highlight
from video_cut.db.models import Video, GenerationVersion
from video_cut.llm import write_highlights
from video_cut.transcribe import transcribe_audio
from video_cut.web.draft import reset_draft_from_highlights
from video_cut.web.session import WebSession, load_session, save_session

# analyze 步骤的默认高光条数与叙事序列总时长预算（秒）：
# provider 请求与卡片预算展示共用这一对常量。
ANALYZE_HIGHLIGHT_COUNT = 15
ANALYZE_DURATION_BUDGET_SECONDS = 300.0


def _sync_highlights_to_db(
    target_dir: Path,
    session: WebSession,
    highlights: list[dict],
) -> None:
    """Sync highlights to database (called after writing to filesystem)."""
    try:
        from video_cut.db.database import get_db
        from video_cut.web.video_service import (
            create_video_from_upload,
            create_generation_version,
            create_highlights_from_analysis,
        )
        
        # Get database session
        db = next(get_db())
        
        try:
            # Find or create video record
            source_filename = session.source_path.split('/')[-1]
            video = db.query(Video).filter(
                Video.original_filename == source_filename
            ).first()
            
            if not video:
                # Create new video record using the service
                video = create_video_from_upload(
                    db=db,
                    original_filename=source_filename,
                    storage_path=session.source_path,
                    file_size=0,  # Will be updated later if needed
                )
            
            # Check if this version already exists
            existing_version = db.query(GenerationVersion).filter(
                GenerationVersion.video_id == video.id,
            ).order_by(GenerationVersion.version_number.desc()).first()
            
            version_number = (existing_version.version_number + 1) if existing_version else 1
            
            # Create generation version
            version = create_generation_version(
                db=db,
                video_id=video.id,
                version_number=version_number,
            )
            
            # Create highlights
            create_highlights_from_analysis(
                db=db,
                video_id=video.id,
                version_id=version.id,
                highlights=highlights,
            )
            
            # Update version status
            version.status = "completed"
            db.commit()
            
            print(f"✓ Synced {len(highlights)} highlights to database for video '{video.original_filename}' v{version.version_number}")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"Warning: Failed to sync highlights to DB: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail the whole process if DB sync fails

# ASR配置现在只需要API Key，OSS相关配置已移除
ASR_CONFIG_KEYS_REQUIRED = ("VIDEO_CUT_DASHSCOPE_API_KEY",)

StepWork = Callable[[], str]
"""任务体：返回 detail 字符串；以 "skipped" 开头则状态记为 skipped。"""


@dataclass(frozen=True)
class StepContext:
    """触发端点交给 work factory 的上下文。"""

    output_dir: Path
    stem: str
    source_path: str
    force: bool
    prompt: str


@dataclass(frozen=True)
class StepDefinition:
    """一个流水线步骤：产物存在性判断 + 任务体工厂。"""

    artifact_done: Callable[[Path], bool]
    build_work: Callable[[StepContext], StepWork]


def _cut_artifact_done(target_dir: Path) -> bool:
    clips_dir = target_dir / paths.CLIPS_DIR_NAME
    return (
        clips_dir.exists()
        and any(clips_dir.glob("*.mp4"))
        and (target_dir / paths.MERGED_FILE_NAME).exists()
    )


def _build_extract_audio_work(context: StepContext) -> StepWork:
    """extract-audio 任务体：复用 pipeline 的 extract_audio，skip 语义同 CLI。"""

    def work() -> str:
        target_dir = context.output_dir / context.stem
        audio_path = target_dir / paths.AUDIO_FILE_NAME
        if audio_path.exists() and not context.force:
            return f"skipped: {audio_path} already exists"
        target_dir.mkdir(parents=True, exist_ok=True)
        extract_audio(Path(context.source_path), audio_path)
        return f"audio extracted: {audio_path}"

    return work


def _build_transcribe_work(context: StepContext) -> StepWork:
    """transcribe 任务体：复用 transcribe_audio + CLI 的 engine 构建。"""

    def work() -> str:
        from video_cut.cli import _build_engine

        target_dir = context.output_dir / context.stem
        audio_path = target_dir / paths.AUDIO_FILE_NAME
        transcript_path = target_dir / paths.TRANSCRIPT_FILE_NAME
        if transcript_path.exists() and not context.force:
            return f"skipped: {transcript_path} already exists"
        if not audio_path.exists():
            raise FileNotFoundError(
                f"{paths.AUDIO_FILE_NAME} not found: {audio_path}. "
                "Run extract-audio first."
            )
        env = _fake_passthrough_env(require_config(ASR_CONFIG_KEYS_REQUIRED))
        engine = _build_engine(env)
        transcribe_audio(audio_path, transcript_path, engine)
        return f"transcript written: {transcript_path}"

    return work


def _build_analyze_work(context: StepContext) -> StepWork:
    """analyze 任务体：复用 provider 构建 + write_highlights。

    提交的提示词先落 session（skip 也保留，预填反映最后一次提交）；
    强制重跑写出新 highlights.json 时同步重置 draft（全部解锁）。
    """

    def work() -> str:
        from video_cut.cli import _build_provider, _trim_to_duration

        target_dir = context.output_dir / context.stem
        transcript_path = target_dir / paths.TRANSCRIPT_FILE_NAME
        highlights_path = target_dir / paths.HIGHLIGHTS_FILE_NAME
        session = load_session(target_dir) or WebSession(source_path=context.source_path)
        session = WebSession(
            source_path=session.source_path,
            analyze_prompt=context.prompt,
            cut_report=session.cut_report,
            cut_report_fingerprint=session.cut_report_fingerprint,
        )
        save_session(target_dir, session)
        if highlights_path.exists() and not context.force:
            return f"skipped: {highlights_path} already exists"
        if not transcript_path.exists():
            raise FileNotFoundError(
                f"{paths.TRANSCRIPT_FILE_NAME} not found: {transcript_path}. "
                "Run transcribe first."
            )
        env = _fake_passthrough_env(require_config(LLM_CONFIG_KEYS))
        provider = _build_provider(env)
        highlights = provider.pick_highlights(
            read_transcript(transcript_path),
            context.prompt,
            ANALYZE_HIGHLIGHT_COUNT,
            ANALYZE_DURATION_BUDGET_SECONDS,
        )
        highlights = _trim_to_duration(
            highlights, ANALYZE_DURATION_BUDGET_SECONDS
        )
        write_highlights(highlights, highlights_path)
        
        # Sync to database
        _sync_highlights_to_db(target_dir, session, highlights)
        
        if (target_dir / paths.HIGHLIGHTS_DRAFT_FILE_NAME).exists():
            # 强制重跑（走到这里即会写新 highlights.json）：旧 draft 会遮蔽
            # 新结果，从新文件重新生成（全部 locked=false）。
            reset_draft_from_highlights(target_dir)
        return f"highlights written: {highlights_path}"

    return work


def _fake_passthrough_env(env: dict[str, str]) -> dict[str, str]:
    """把测试 fake 的环境变量透传到 CLI 构建器（与 config 前缀隔离一致）。"""
    return {
        **env,
        **{
            key: os.environ[key]
            for key in (
                "VIDEO_CUT_ASR_ENGINE_FAKE",
                "VIDEO_CUT_LLM_PROVIDER_FAKE",
                "VIDEO_CUT_OSS_FAKE_DIR",
            )
            if key in os.environ
        },
    }


def _unwired_cut_work(context: StepContext) -> StepWork:
    raise ValueError(
        "cut is triggered via /videos/{stem}/cut, not the steps endpoint"
    )


def build_run_to_highlights_work(context: StepContext) -> StepWork:
    """一键跑到 highlights：顺序执行 extract-audio → transcribe → analyze。

    不进 STEP_REGISTRY/STEP_NAMES（它不是一个步骤卡片）；skip 语义来自各
    子 work 自身（force=False），任一异常直接上抛让 TaskRunner 记 failed。
    prompt 优先取 context.prompt（ACT-01「生成高光」表单直传）；为空时回
    退 session 已存的 analyze_prompt。三段子 work 的 detail 逐行标注步骤名
    后用 ``\\n`` join 返回（标注避免首个子步 skip 时整个任务被 TaskRunner
    误判为 skipped——组合任务跑完整条链即视为 done）。
    """

    def work() -> str:
        target_dir = context.output_dir / context.stem
        session = load_session(target_dir) or WebSession(
            source_path=context.source_path
        )
        prompt = context.prompt or session.analyze_prompt
        sub_context = StepContext(
            output_dir=context.output_dir,
            stem=context.stem,
            source_path=context.source_path,
            force=False,
            prompt=prompt,
        )
        details = [
            f"{step_name}: {STEP_REGISTRY[step_name].build_work(sub_context)()}"
            for step_name in ("extract-audio", "transcribe", "analyze")
        ]
        return "\n".join(details)

    return work


STEP_REGISTRY: dict[str, StepDefinition] = {
    "extract-audio": StepDefinition(
        artifact_done=lambda d: (d / paths.AUDIO_FILE_NAME).exists(),
        build_work=_build_extract_audio_work,
    ),
    "transcribe": StepDefinition(
        artifact_done=lambda d: (d / paths.TRANSCRIPT_FILE_NAME).exists(),
        build_work=_build_transcribe_work,
    ),
    "analyze": StepDefinition(
        artifact_done=lambda d: (d / paths.HIGHLIGHTS_FILE_NAME).exists(),
        build_work=_build_analyze_work,
    ),
    # cut 由两段式 /cut 端点执行；此处只登记产物判断供卡片状态展示。
    "cut": StepDefinition(
        artifact_done=_cut_artifact_done,
        build_work=_unwired_cut_work,
    ),
}

STEP_NAMES = tuple(STEP_REGISTRY)


def cut_highlights_work(
    output_dir: Path, 
    stem: str, 
    source: Path, 
    final_highlights: list[Highlight],
    subtitles: bool = False,
) -> StepWork:
    """cut 任务体：清旧产物后全量重切（与 CLI --force 同语义）。
    
    Args:
        output_dir: Output directory
        stem: Video stem name
        source: Source video path
        final_highlights: List of highlights to cut
        subtitles: Whether to burn subtitles into clips
    """

    def work() -> str:
        from video_cut.cutting import cut_highlights, merge_segments
        from video_cut.subtitles import generate_srt_from_transcript, burn_subtitles_into_video
        import json

        target_dir = output_dir / stem
        clips_dir = target_dir / paths.CLIPS_DIR_NAME
        merged_path = target_dir / paths.MERGED_FILE_NAME
        transcript_path = target_dir / paths.TRANSCRIPT_FILE_NAME
        
        if clips_dir.exists():
            for old_clip in clips_dir.glob("*.mp4"):
                old_clip.unlink()
        merged_path.unlink(missing_ok=True)
        
        clip_paths = cut_highlights(source, final_highlights, clips_dir)
        
        # If subtitles are enabled and transcript exists, burn subtitles into clips
        if subtitles and transcript_path.exists():
            subtitled_clips_dir = clips_dir / "subtitled"
            subtitled_clips_dir.mkdir(parents=True, exist_ok=True)
            
            with open(transcript_path, encoding="utf-8") as f:
                transcript_data = json.load(f)
            
            new_clip_paths = []
            for i, (clip_path, highlight) in enumerate(zip(clip_paths, final_highlights), 1):
                # Generate SRT for this specific clip
                srt_path = subtitled_clips_dir / f"clip_{i:02d}.srt"
                highlight_segment = {"start": highlight.start, "end": highlight.end}
                generate_srt_from_transcript(
                    transcript_data, 
                    srt_path, 
                    [highlight_segment]
                )
                
                # Burn subtitles into the clip
                subtitled_clip_path = subtitled_clips_dir / clip_path.name
                burn_subtitles_into_video(clip_path, srt_path, subtitled_clip_path)
                new_clip_paths.append(subtitled_clip_path)
            
            clip_paths = new_clip_paths
        
        merge_segments(clip_paths, merged_path)
        
        # Update database with clip file paths
        _update_clip_paths_in_db(stem, clip_paths, merged_path)
        
        return f"cut done: {len(clip_paths)} clips, merged: {merged_path}"

    return work


def _update_clip_paths_in_db(
    stem: str,
    clip_paths: list[Path],
    merged_path: Path,
) -> None:
    """Update ClipVersion records with actual file paths after cutting."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        
        from video_cut.config import get_settings
        from video_cut.db.models import Video, GenerationVersion, Highlight, ClipVersion
        
        settings = get_settings()
        
        if not settings.database_url:
            print("Warning: No database configured, skipping clip path update")
            return
        
        engine = create_engine(settings.database_url)
        
        with Session(engine) as db:
            # Find video by stem (original_filename without extension)
            video_filename = stem + ".mp4"  # Assume mp4
            video = db.query(Video).filter(
                Video.original_filename.like(f"%{stem}%")
            ).first()
            
            if not video:
                print(f"Warning: Video not found for stem {stem}")
                return
            
            # Get active version
            version = db.query(GenerationVersion).filter(
                GenerationVersion.video_id == video.id,
                GenerationVersion.is_active == True,
            ).first()
            
            if not version:
                print(f"Warning: No active version found for video {video.id}")
                return
            
            # Get highlights for this video
            highlights = db.query(Highlight).filter(
                Highlight.video_id == video.id
            ).order_by(Highlight.order_index).all()
            
            # Update clip versions with file paths
            for idx, (highlight, clip_path) in enumerate(zip(highlights, clip_paths)):
                clip = db.query(ClipVersion).filter(
                    ClipVersion.generation_version_id == version.id,
                    ClipVersion.highlight_id == highlight.id,
                ).first()
                
                if clip:
                    clip.clip_path = str(clip_path)
                    # If subtitled version exists, update that too
                    subtitled_path = clip_path.parent / "subtitled" / clip_path.name
                    if subtitled_path.exists():
                        clip.subtitled_clip_path = str(subtitled_path)
            
            # Update version with merged video path
            version.merged_video_path = str(merged_path)
            version.file_size = merged_path.stat().st_size if merged_path.exists() else 0
            
            db.commit()
            print(f"✓ Updated clip paths in database for {stem}")
            
    except Exception as e:
        print(f"Warning: Failed to update clip paths in DB: {e}")
        import traceback
        traceback.print_exc()
