"""Orchestration for the transcribe command: engine + artifact."""

from __future__ import annotations

from pathlib import Path

from video_cut.asr import Engine, write_transcript


def transcribe_audio(
    audio_path: Path,
    transcript_path: Path,
    engine: Engine,
) -> None:
    """Transcribe audio file via the engine, write transcript.json.

    For real-time engines (paraformer-realtime-v2), the engine reads the
    local audio file directly without requiring OSS storage.
    For traditional engines (paraformer-v2), audio is served via local HTTP server.
    """
    # Check engine type to determine how to provide the audio
    engine_type = type(engine).__name__
    
    if "Realtime" in engine_type:
        # Real-time engines read local files directly
        transcript = engine.transcribe(str(audio_path))
    else:
        # Standard engines need a URL - use local HTTP server
        from video_cut.http_storage import LocalHttpAudioServer
        
        http_server = LocalHttpAudioServer.get_instance()
        audio_url = http_server.upload(audio_path)
        
        try:
            transcript = engine.transcribe(audio_url)
        finally:
            # Clean up staged file
            http_server.delete(audio_url)
    
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    write_transcript(transcript, transcript_path)
