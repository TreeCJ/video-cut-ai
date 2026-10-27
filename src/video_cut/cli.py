"""video-cut command-line interface."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import typer

from video_cut.align import align_highlights
from video_cut.asr import read_transcript
from video_cut.audio import extract_audio
from video_cut.config import (
    ASR_CONFIG_KEYS_REQUIRED,
    ASR_MODEL_KEY,
    DEFAULT_ASR_MODEL,
    DEFAULT_LLM_MODEL,
    LLM_MODEL_KEY,
    LLM_CONFIG_KEYS,
    MissingConfigError,
    _load_env,
    require_config,
)
from video_cut import paths
from video_cut.cutting import (
    DEFAULT_CONCURRENCY,
    Highlight,
    cut_highlights,
    load_highlights,
    merge_segments,
)
from video_cut.subtitles import generate_srt_from_transcript, burn_subtitles_into_video
from video_cut.transcribe import transcribe_audio

app = typer.Typer(
    name="video-cut",
    help="Extract highlight clips from long videos, locally.",
    no_args_is_help=True,
)


def main() -> None:
    app()


def _resolve_model(env: dict[str, str], key: str, default: str) -> str:
    """Resolve a model name: process env > .env > built-in default.

    ``env`` holds only the required keys (see require_config), so optional
    overrides are looked up in the merged .env + process environment.
    """
    return _load_env().get(key) or env.get(key) or default


def _build_engine(env: dict[str, str]):
    """Build the ASR engine from configuration.

    Tests inject a fake engine via the VIDEO_CUT_ASR_ENGINE_FAKE env var so the
    CLI seam can be exercised without network access.
    """
    import json

    from video_cut.asr import Sentence, Transcript, Word

    fake_json = env.get("VIDEO_CUT_ASR_ENGINE_FAKE")
    if fake_json is not None:

        class FakeEngine:
            def __init__(self, payload: dict) -> None:
                self._payload = payload
                self.urls: list[str] = []

            def transcribe(self, audio_url: str) -> Transcript:
                self.urls.append(audio_url)
                urls_file = os.environ.get("_VIDEO_CUT_FAKE_ENGINE_URLS_FILE")
                if urls_file:
                    Path(urls_file).write_text("\n".join(self.urls), encoding="utf-8")
                if self._payload.get("error"):
                    raise RuntimeError(self._payload["error"])
                return Transcript(
                    sentences=tuple(Sentence(**s) for s in self._payload["sentences"]),
                    words=tuple(Word(**w) for w in self._payload["words"]),
                )

        engine = FakeEngine(json.loads(fake_json))
        return engine

    # Check if using real-time model
    asr_model = _resolve_model(env, ASR_MODEL_KEY, DEFAULT_ASR_MODEL)
    
    if "realtime" in asr_model:
        # Use real-time engine for paraformer-realtime-v2
        from video_cut.asr.paraformer_realtime import ParaformerRealtimeEngine
        
        return ParaformerRealtimeEngine(
            api_key=env["VIDEO_CUT_DASHSCOPE_API_KEY"],
            model=asr_model,
        )
    else:
        # Use standard engine for paraformer-v2 with local HTTP server
        from video_cut.asr.paraformer_standard import ParaformerStandardEngine
        from video_cut.http_storage import LocalHttpAudioServer
        
        # Setup local HTTP server for audio files
        http_server = LocalHttpAudioServer.get_instance()
        
        # Try to setup ngrok for public HTTPS URL (optional)
        ngrok_token = env.get("VIDEO_CUT_NGROK_AUTH_TOKEN")
        if ngrok_token:
            from video_cut.http_storage import setup_ngrok_tunnel
            public_url = setup_ngrok_tunnel(ngrok_token)
            if public_url:
                http_server.public_url = public_url
        
        return ParaformerStandardEngine(
            api_key=env["VIDEO_CUT_DASHSCOPE_API_KEY"],
            model=asr_model,
        )


def _build_provider(env: dict[str, str]):
    """Build the LLM provider from configuration.

    Tests inject a fake provider via the VIDEO_CUT_LLM_PROVIDER_FAKE env var
    so the CLI seam can be exercised without network access. The fake payload
    is either a JSON list of highlights (the canned reply) or
    {"raw_text": "<string>"} to replay a malformed LLM reply verbatim —
    parse errors must surface the same way as with the real provider.
    """
    import json

    fake_json = env.get("VIDEO_CUT_LLM_PROVIDER_FAKE")
    if fake_json is not None:
        from video_cut.asr import Transcript
        from video_cut.llm import parse_highlights

        class FakeProvider:
            def __init__(self, payload, model: str) -> None:
                self._payload = payload
                self.calls: list[dict] = []
                model_file = os.environ.get("_VIDEO_CUT_FAKE_PROVIDER_MODEL_FILE")
                if model_file:
                    Path(model_file).write_text(model, encoding="utf-8")

            def pick_highlights(
                self,
                transcript: Transcript,
                user_prompt: str,
                count: int,
                max_duration: float,
            ) -> list[Highlight]:
                self.calls.append(
                    {
                        "count": count,
                        "max_duration": max_duration,
                        "user_prompt": user_prompt,
                        "sentence_count": len(transcript.sentences),
                    }
                )
                calls_file = os.environ.get("_VIDEO_CUT_FAKE_PROVIDER_CALLS_FILE")
                if calls_file:
                    Path(calls_file).write_text(
                        json.dumps(self.calls), encoding="utf-8"
                    )
                # {"raw_text": ...} routes through the real parser so malformed
                # LLM output fails exactly as it would from QwenProvider.
                if isinstance(self._payload, dict) and "raw_text" in self._payload:
                    return parse_highlights(self._payload["raw_text"])
                return [Highlight(**item) for item in self._payload]

        return FakeProvider(
            json.loads(fake_json), _resolve_model(env, LLM_MODEL_KEY, DEFAULT_LLM_MODEL)
        )

    from video_cut.llm import QwenProvider

    return QwenProvider(
        api_key=env["VIDEO_CUT_DASHSCOPE_API_KEY"],
        model=_resolve_model(env, LLM_MODEL_KEY, DEFAULT_LLM_MODEL),
    )


@app.command("extract-audio")
def extract_audio_command(
    video: Path = typer.Argument(..., exists=True, dir_okay=False, help="Input video file."),
    output_dir: Path = typer.Option(
        Path("output"), "--output-dir", "-o", help="Base output directory."
    ),
    force: bool = typer.Option(
        False, "--force", help="Re-run even if the artifact already exists."
    ),
) -> None:
    """Extract 16kHz mono m4a audio from a video for ASR."""
    target_dir = output_dir / video.stem
    audio_path = target_dir / paths.AUDIO_FILE_NAME

    if audio_path.exists() and not force:
        typer.echo(f"Skipping: {audio_path} already exists (use --force to re-run).")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    extract_audio(video, audio_path)
    typer.echo(f"Audio extracted: {audio_path}")


@app.command("transcribe")
def transcribe_command(
    video: Path = typer.Argument(..., exists=True, dir_okay=False, help="Input video file."),
    output_dir: Path = typer.Option(
        Path("output"), "--output-dir", "-o", help="Base output directory."
    ),
    force: bool = typer.Option(
        False, "--force", help="Re-run even if the artifact already exists."
    ),
) -> None:
    """Transcribe extracted audio via the configured ASR engine."""
    try:
        env = require_config(ASR_CONFIG_KEYS_REQUIRED)
    except MissingConfigError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    # Test-injection keys live outside the required set; pull them from the
    # process env. Model overrides are resolved separately (see _resolve_model).
    env = {
        **env,
        **{
            key: os.environ[key]
            for key in ("VIDEO_CUT_ASR_ENGINE_FAKE", "VIDEO_CUT_OSS_FAKE_DIR")
            if key in os.environ
        },
    }

    target_dir = output_dir / video.stem
    audio_path = target_dir / paths.AUDIO_FILE_NAME
    transcript_path = target_dir / paths.TRANSCRIPT_FILE_NAME

    if transcript_path.exists() and not force:
        typer.echo(f"Skipping: {transcript_path} already exists (use --force to re-run).")
        return

    if not audio_path.exists():
        typer.echo(
            f"Audio not found: {audio_path}. Run extract-audio first.", err=True
        )
        raise typer.Exit(code=1)

    engine = _build_engine(env)
    try:
        transcribe_audio(audio_path, transcript_path, engine)
    except Exception as error:
        typer.echo(f"Transcription failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Transcript written: {transcript_path}")


def _trim_to_duration(
    highlights: list[Highlight], max_duration: float
) -> list[Highlight]:
    """Drop trailing highlights until the total duration fits the budget.

    The LLM estimates durations loosely, so the prompt's budget alone can
    overshoot; this is the programmatic backstop. Trimming from the end keeps
    the narrative opening intact. Returns the input unchanged when it fits.
    """
    kept: list[Highlight] = []
    total = 0.0
    overflowed = False
    for highlight in highlights:
        duration = highlight.end - highlight.start
        # The first clip always stays: an empty result is worse than an
        # over-budget one — the user can trim highlights.json by hand.
        if not overflowed and (not kept or total + duration <= max_duration):
            kept.append(highlight)
            total += duration
        else:
            overflowed = True
    dropped = len(highlights) - len(kept)
    if dropped > 0:
        typer.echo(
            f"Duration warning: dropped {dropped} clip(s) exceeding the "
            f"{max_duration:.0f}s total budget (kept {total:.1f}s). "
            f"Edit {paths.HIGHLIGHTS_FILE_NAME} to adjust manually.",
            err=True,
        )
    return kept


@app.command("analyze")
def analyze_command(
    video: Path = typer.Argument(..., exists=True, dir_okay=False, help="Input video file."),
    output_dir: Path = typer.Option(
        Path("output"), "--output-dir", "-o", help="Base output directory."
    ),
    prompt: str = typer.Option(
        "",
        "--prompt",
        "-p",
        help="Natural-language direction layered on the built-in highlight criteria.",
    ),
    count: int = typer.Option(
        15, "--count", min=1, help="Maximum number of highlight clips."
    ),
    max_duration: float = typer.Option(
        300.0,
        "--max-duration",
        min=1,
        help="Maximum total duration (seconds) of the merged highlight reel.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Re-run even if the artifact already exists."
    ),
) -> None:
    """Pick highlights from the transcript via the configured LLM."""
    try:
        env = require_config(LLM_CONFIG_KEYS)
    except MissingConfigError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    # Test-injection keys live outside the required set; pull them from the
    # process env. Model overrides are resolved separately (see _resolve_model).
    env = {
        **env,
        **{
            key: os.environ[key]
            for key in ("VIDEO_CUT_LLM_PROVIDER_FAKE",)
            if key in os.environ
        },
    }

    target_dir = output_dir / video.stem
    transcript_path = target_dir / paths.TRANSCRIPT_FILE_NAME
    highlights_path = target_dir / paths.HIGHLIGHTS_FILE_NAME

    if highlights_path.exists() and not force:
        typer.echo(f"Skipping: {highlights_path} already exists (use --force to re-run).")
        return

    if not transcript_path.exists():
        typer.echo(
            f"{paths.TRANSCRIPT_FILE_NAME} not found: {transcript_path}. Run transcribe first.",
            err=True,
        )
        raise typer.Exit(code=1)

    from video_cut.llm import HighlightAnalysisError, write_highlights

    provider = _build_provider(env)
    try:
        highlights = provider.pick_highlights(
            read_transcript(transcript_path), prompt, count, max_duration
        )
    except HighlightAnalysisError as error:
        typer.echo(f"Analysis failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    except Exception as error:
        typer.echo(f"Analysis failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    highlights = _trim_to_duration(highlights, max_duration)

    write_highlights(highlights, highlights_path)
    typer.echo(f"Highlights written: {highlights_path}")
    for index, highlight in enumerate(highlights, start=1):
        typer.echo(
            f"  {index}. {highlight.title} "
            f"({highlight.start:.1f}s - {highlight.end:.1f}s): {highlight.reason}"
        )

    from video_cut.overlap import find_overlaps

    for a, b, shared in find_overlaps(highlights):
        typer.echo(
            f"Overlap warning: '{a.title}' and '{b.title}' share "
            f"{shared:.1f}s — the clips will be near-duplicates. "
            f"Edit {paths.HIGHLIGHTS_FILE_NAME} to drop or retime one.",
            err=True,
        )


@app.command("cut")
def cut_command(
    video: Path = typer.Argument(..., exists=True, dir_okay=False, help="Input video file."),
    output_dir: Path = typer.Option(
        Path("output"), "--output-dir", "-o", help="Base output directory."
    ),
    force: bool = typer.Option(
        False, "--force", help="Re-run even if the artifacts already exist."
    ),
    concurrency: int = typer.Option(
        DEFAULT_CONCURRENCY,
        "--concurrency",
        min=1,
        help="Maximum number of parallel slice jobs.",
    ),
    subtitles: bool = typer.Option(
        False, "--subtitles/--no-subtitles", help="Burn subtitles into final merged video."
    ),
) -> None:
    """Cut highlights into clips and merge them into a single video."""
    target_dir = output_dir / video.stem
    highlights_path = target_dir / paths.HIGHLIGHTS_FILE_NAME
    clips_dir = target_dir / paths.CLIPS_DIR_NAME
    merged_path = target_dir / paths.MERGED_FILE_NAME

    if not highlights_path.exists():
        typer.echo(
            f"{paths.HIGHLIGHTS_FILE_NAME} not found: {highlights_path}. Run analyze first.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        highlights = load_highlights(highlights_path)
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

    # Quote-anchor alignment (spec: 时间戳对齐): when transcript.json exists,
    # correct LLM timestamps against the actual sentence positions. Without a
    # transcript, cut stays usable standalone on the raw timestamps.
    transcript_path = target_dir / paths.TRANSCRIPT_FILE_NAME
    if transcript_path.exists():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            aligned = align_highlights(highlights, read_transcript(transcript_path))
        for warning in caught:
            typer.echo(f"Warning: {warning.message}", err=True)
        highlights = aligned
    else:
        typer.echo(
            f"Warning: {paths.TRANSCRIPT_FILE_NAME} not found: {transcript_path}. "
            f"Using raw LLM timestamps without alignment.",
            err=True,
        )

    expected_clips_done = clips_dir.exists() and len(
        list(clips_dir.glob("*.mp4"))
    ) == len(highlights)
    if expected_clips_done and merged_path.exists() and not force:
        typer.echo(
            f"Skipping: clips and {merged_path} already exist "
            f"(use --force to re-run)."
        )
        return

    if force and clips_dir.exists():
        for old_clip in clips_dir.glob("*.mp4"):
            old_clip.unlink()

    clip_paths = cut_highlights(video, highlights, clips_dir, concurrency=concurrency)
    for clip_path in clip_paths:
        typer.echo(f"Clip cut: {clip_path}")

    # If subtitles are enabled, burn them into each clip before merging
    if subtitles and transcript_path.exists():
        typer.echo("Burning subtitles into clips...")
        subtitled_clips_dir = clips_dir / "subtitled"
        subtitled_clips_dir.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(transcript_path, encoding="utf-8") as f:
            transcript_data = json.load(f)
        
        new_clip_paths = []
        for i, (clip_path, highlight) in enumerate(zip(clip_paths, highlights), 1):
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
            typer.echo(f"Subtitled clip: {subtitled_clip_path}")
        
        clip_paths = new_clip_paths

    merge_segments(clip_paths, merged_path)
    typer.echo(f"Merged video written: {merged_path}")


@app.command("serve")
def serve_command(
    port: int = typer.Option(8462, "--port", help="Port to bind on 127.0.0.1."),
    output_dir: Path = typer.Option(
        Path("output"), "--output-dir", "-o", help="Base output directory."
    ),
    reload: bool = typer.Option(
        True, "--reload/--no-reload", help="Auto-restart on code changes (dev)."
    ),
) -> None:
    """Start the local web workbench (server-rendered HTML + HTMX)."""
    import uvicorn

    typer.echo(f"Serving video-cut web UI at http://127.0.0.1:{port}")
    if reload:
        uvicorn.run(
            "video_cut.web:create_app_dev",
            factory=True,
            host="127.0.0.1",
            port=port,
            reload=True,
            reload_dirs=["src"],
        )
    else:
        from video_cut.web import create_app

        uvicorn.run(create_app(output_dir), host="127.0.0.1", port=port)


@app.command("run")
def run_command(
    video: Path = typer.Argument(..., exists=True, dir_okay=False, help="Input video file."),
    output_dir: Path = typer.Option(
        Path("output"), "--output-dir", "-o", help="Base output directory."
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Run straight through to clips and merged.mp4 with no human checkpoint.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Re-run the whole chain even if artifacts exist."
    ),
    prompt: str = typer.Option(
        "",
        "--prompt",
        "-p",
        help="Natural-language direction layered on the built-in highlight criteria.",
    ),
    count: int = typer.Option(
        15, "--count", min=1, help="Maximum number of highlight clips."
    ),
    max_duration: float = typer.Option(
        300.0,
        "--max-duration",
        min=1,
        help="Maximum total duration (seconds) of the merged highlight reel.",
    ),
    concurrency: int = typer.Option(
        DEFAULT_CONCURRENCY,
        "--concurrency",
        min=1,
        help="Maximum number of parallel slice jobs.",
    ),
) -> None:
    """Run the whole pipeline: extract-audio, transcribe, analyze, then cut.

    Without --auto the run stops after analyze and prints the highlight list;
    review or edit highlights.json, then continue with `video-cut cut`.
    """
    extract_audio_command(video=video, output_dir=output_dir, force=force)
    transcribe_command(video=video, output_dir=output_dir, force=force)
    analyze_command(
        video=video,
        output_dir=output_dir,
        prompt=prompt,
        count=count,
        max_duration=max_duration,
        force=force,
    )

    if not auto:
        highlights_path = output_dir / video.stem / paths.HIGHLIGHTS_FILE_NAME
        typer.echo("")
        typer.echo(
            f"Run paused: review or edit {highlights_path}, then continue with:"
        )
        typer.echo(
            f"  video-cut cut {video} --output-dir {output_dir}"
        )
        return

    cut_command(
        video=video, output_dir=output_dir, force=force, concurrency=concurrency
    )
