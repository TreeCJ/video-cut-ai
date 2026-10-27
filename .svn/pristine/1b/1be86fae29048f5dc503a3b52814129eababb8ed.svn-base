#!/usr/bin/env python
"""Test paraformer-realtime-v2 engine with a local audio file."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_realtime_engine():
    """Test the real-time ASR engine with a sample audio file."""
    from video_cut.asr.paraformer_realtime import ParaformerRealtimeEngine
    from video_cut.config import _load_env

    # Load configuration
    env = _load_env()
    api_key = env.get("VIDEO_CUT_DASHSCOPE_API_KEY")

    if not api_key:
        print("❌ No API key configured")
        return False

    print(f"✓ API Key loaded: {api_key[:15]}...")

    # Create engine
    try:
        engine = ParaformerRealtimeEngine(
            api_key=api_key,
            model="paraformer-realtime-v2",
        )
        print("✓ Real-time engine created successfully")
    except Exception as e:
        print(f"❌ Failed to create engine: {e}")
        return False

    # Test with a sample audio file (if exists)
    test_audio = Path("test_audio.wav")
    if not test_audio.exists():
        print(f"\n⚠️  No test audio file found at: {test_audio}")
        print("\nTo test, place a WAV file named 'test_audio.wav' in the project root")
        print("Then run this script again.\n")
        return True

    print(f"\n🎤 Transcribing: {test_audio}")
    try:
        transcript = engine.transcribe(test_audio)
        print(f"✓ Transcription successful!")
        print(f"  - Sentences: {len(transcript.sentences)}")
        print(f"  - Words: {len(transcript.words)}")

        # Show first few sentences
        if transcript.sentences:
            print("\n📝 First 3 sentences:")
            for i, sent in enumerate(transcript.sentences[:3], 1):
                print(f"  {i}. [{sent.begin_time:.2f}s-{sent.end_time:.2f}s] {sent.text}")

        return True

    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Paraformer Real-time v2 Engine")
    print("=" * 60)
    print()

    success = test_realtime_engine()

    print()
    print("=" * 60)
    if success:
        print("✅ Test completed successfully!")
    else:
        print("❌ Test failed")
    print("=" * 60)

    sys.exit(0 if success else 1)
