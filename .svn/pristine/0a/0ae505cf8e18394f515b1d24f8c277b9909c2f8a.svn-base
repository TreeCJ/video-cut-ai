"""Tests for the analyze command at the CLI seam.

The LLM is replaced by a fake Provider injected via env config:
- VIDEO_CUT_LLM_PROVIDER_FAKE: canned response — either a JSON list of
  highlights (shape locked to the Highlight contract) or
  {"raw_text": "<string>"} to simulate a malformed LLM reply verbatim.

No test touches the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from video_cut.cli import app

TRANSCRIPT_PAYLOAD = {
    "sentences": [
        {"begin_time": 0.5, "end_time": 2.0, "text": "大家好，欢迎来到本期视频。"},
        {"begin_time": 2.5, "end_time": 5.0, "text": "其实90%的人都搞错了。"},
        {"begin_time": 5.5, "end_time": 9.0, "text": "今天我们把这个问题讲透。"},
    ],
    "words": [
        {"begin_time": 0.5, "end_time": 0.8, "word": "大家"},
        {"begin_time": 2.5, "end_time": 2.8, "word": "其实"},
    ],
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
def fake_llm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scrub real cloud config, then inject the fake Provider."""
    monkeypatch.delenv("VIDEO_CUT_DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("VIDEO_CUT_LLM_MODEL", raising=False)
    monkeypatch.chdir(tmp_path)  # isolate from any real .env in the repo root

    monkeypatch.setenv("VIDEO_CUT_DASHSCOPE_API_KEY", "fake-dashscope-key")
    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps(CANNED_HIGHLIGHTS)
    )


def _stage_transcript(output_dir: Path, video: Path) -> Path:
    """Stage a pre-existing transcript.json as if transcribe already ran."""
    target_dir = output_dir / video.stem
    target_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = target_dir / "transcript.json"
    transcript_path.write_text(
        json.dumps(TRANSCRIPT_PAYLOAD, ensure_ascii=False), encoding="utf-8"
    )
    return transcript_path


def test_analyze_writes_highlights_json_matching_the_contract(
    cli_runner: CliRunner, fixture_video: Path, fake_llm: None, tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)

    result = cli_runner.invoke(
        app, ["analyze", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code == 0, result.output
    highlights_path = output_dir / fixture_video.stem / "highlights.json"
    assert highlights_path.exists()

    highlights = json.loads(highlights_path.read_text(encoding="utf-8"))
    assert highlights == CANNED_HIGHLIGHTS
    for item in highlights:
        assert set(item) == {"title", "reason", "quote", "start", "end"}
        assert isinstance(item["start"], (int, float))
        assert isinstance(item["end"], (int, float))
        assert item["start"] < item["end"]


def test_analyze_passes_count_to_the_provider(
    cli_runner: CliRunner,
    fixture_video: Path,
    fake_llm: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls_file = tmp_path / "provider-calls.json"
    monkeypatch.setenv("_VIDEO_CUT_FAKE_PROVIDER_CALLS_FILE", str(calls_file))
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)

    result = cli_runner.invoke(
        app,
        [
            "analyze",
            str(fixture_video),
            "--output-dir",
            str(output_dir),
            "--count",
            "5",
        ],
    )

    assert result.exit_code == 0, result.output
    calls = json.loads(calls_file.read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert calls[0]["count"] == 5


def test_analyze_count_defaults_to_ten(
    cli_runner: CliRunner,
    fixture_video: Path,
    fake_llm: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls_file = tmp_path / "provider-calls.json"
    monkeypatch.setenv("_VIDEO_CUT_FAKE_PROVIDER_CALLS_FILE", str(calls_file))
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)

    result = cli_runner.invoke(
        app, ["analyze", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code == 0, result.output
    calls = json.loads(calls_file.read_text(encoding="utf-8"))
    assert calls[0]["count"] == 15
    assert calls[0]["max_duration"] == 300.0


def test_analyze_passes_max_duration_to_the_provider(
    cli_runner: CliRunner,
    fixture_video: Path,
    fake_llm: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls_file = tmp_path / "provider-calls.json"
    monkeypatch.setenv("_VIDEO_CUT_FAKE_PROVIDER_CALLS_FILE", str(calls_file))
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)

    result = cli_runner.invoke(
        app,
        [
            "analyze",
            str(fixture_video),
            "--output-dir",
            str(output_dir),
            "--max-duration",
            "120",
        ],
    )

    assert result.exit_code == 0, result.output
    calls = json.loads(calls_file.read_text(encoding="utf-8"))
    assert calls[0]["max_duration"] == 120.0


def test_analyze_trims_clips_exceeding_the_duration_budget(
    cli_runner: CliRunner,
    fixture_video: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clips past the budget are dropped from the end, with a warning."""
    monkeypatch.delenv("VIDEO_CUT_DASHSCOPE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIDEO_CUT_DASHSCOPE_API_KEY", "fake-dashscope-key")
    over_budget = [
        {"title": "a", "reason": "r", "quote": "q", "start": 0.0, "end": 100.0},
        {"title": "b", "reason": "r", "quote": "q", "start": 100.0, "end": 200.0},
        {"title": "c", "reason": "r", "quote": "q", "start": 200.0, "end": 400.0},
    ]
    monkeypatch.setenv("VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps(over_budget))
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)

    result = cli_runner.invoke(
        app,
        [
            "analyze",
            str(fixture_video),
            "--output-dir",
            str(output_dir),
            "--max-duration",
            "250",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Duration warning" in result.output
    highlights = json.loads(
        (output_dir / fixture_video.stem / "highlights.json").read_text(
            encoding="utf-8"
        )
    )
    assert [item["title"] for item in highlights] == ["a", "b"]


def test_analyze_keeps_first_clip_even_if_it_alone_exceeds_the_budget(
    cli_runner: CliRunner,
    fixture_video: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty result is worse than an over-budget one: clip 1 always stays."""
    monkeypatch.delenv("VIDEO_CUT_DASHSCOPE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIDEO_CUT_DASHSCOPE_API_KEY", "fake-dashscope-key")
    oversized = [
        {"title": "a", "reason": "r", "quote": "q", "start": 0.0, "end": 500.0},
    ]
    monkeypatch.setenv("VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps(oversized))
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)

    result = cli_runner.invoke(
        app,
        [
            "analyze",
            str(fixture_video),
            "--output-dir",
            str(output_dir),
            "--max-duration",
            "60",
        ],
    )

    assert result.exit_code == 0, result.output
    highlights = json.loads(
        (output_dir / fixture_video.stem / "highlights.json").read_text(
            encoding="utf-8"
        )
    )
    assert [item["title"] for item in highlights] == ["a"]


def test_analyze_fails_clearly_on_malformed_llm_json(
    cli_runner: CliRunner,
    fixture_video: Path,
    fake_llm: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "VIDEO_CUT_LLM_PROVIDER_FAKE",
        json.dumps({"raw_text": "这不是 JSON，模型跑飞了 [{}}]"}),
    )
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)

    result = cli_runner.invoke(
        app, ["analyze", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code != 0
    assert "not valid JSON" in result.output or "malformed" in result.output
    # No partial artifact is left behind.
    assert not (output_dir / fixture_video.stem / "highlights.json").exists()


def test_analyze_skips_when_highlights_exist(
    cli_runner: CliRunner,
    fixture_video: Path,
    fake_llm: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls_file = tmp_path / "provider-calls.json"
    monkeypatch.setenv("_VIDEO_CUT_FAKE_PROVIDER_CALLS_FILE", str(calls_file))
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)
    highlights_path = output_dir / fixture_video.stem / "highlights.json"
    highlights_path.write_text("[]", encoding="utf-8")

    result = cli_runner.invoke(
        app, ["analyze", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code == 0, result.output
    assert "Skipping" in result.output
    # The provider was never called.
    assert not calls_file.exists()


def test_analyze_force_reruns_when_highlights_exist(
    cli_runner: CliRunner, fixture_video: Path, fake_llm: None, tmp_path: Path
) -> None:
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)
    highlights_path = output_dir / fixture_video.stem / "highlights.json"
    highlights_path.write_text("[]", encoding="utf-8")

    result = cli_runner.invoke(
        app,
        ["analyze", str(fixture_video), "--output-dir", str(output_dir), "--force"],
    )

    assert result.exit_code == 0, result.output
    highlights = json.loads(highlights_path.read_text(encoding="utf-8"))
    assert highlights == CANNED_HIGHLIGHTS


def test_analyze_fails_when_transcript_missing(
    cli_runner: CliRunner, fixture_video: Path, fake_llm: None, tmp_path: Path
) -> None:
    result = cli_runner.invoke(
        app,
        ["analyze", str(fixture_video), "--output-dir", str(tmp_path / "output")],
    )

    assert result.exit_code != 0
    assert "transcribe" in result.output


def test_analyze_uses_llm_model_from_env_file(
    cli_runner: CliRunner,
    fixture_video: Path,
    fake_llm: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM_MODEL set in .env (not the process env) must reach the provider.

    The fake provider is injected, so the model does not reach the network —
    the assertion observes the resolved model recorded at build time.
    """
    model_file = tmp_path / "model.txt"
    monkeypatch.setenv("_VIDEO_CUT_FAKE_PROVIDER_MODEL_FILE", str(model_file))
    monkeypatch.delenv("VIDEO_CUT_LLM_MODEL", raising=False)
    # fake_llm chdir'd into tmp_path, so this .env is what _load_env reads.
    (tmp_path / ".env").write_text(
        "VIDEO_CUT_DASHSCOPE_API_KEY=fake-dashscope-key\nVIDEO_CUT_LLM_MODEL=qwen-max\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"
    _stage_transcript(output_dir, fixture_video)

    result = cli_runner.invoke(
        app, ["analyze", str(fixture_video), "--output-dir", str(output_dir)]
    )

    assert result.exit_code == 0, result.output
    assert model_file.read_text(encoding="utf-8") == "qwen-max"


def test_analyze_warns_when_highlights_overlap(
    cli_runner: CliRunner, fixture_video: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Overlapping picks (the live-run duplication) surface a warning."""
    monkeypatch.delenv("VIDEO_CUT_DASHSCOPE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIDEO_CUT_DASHSCOPE_API_KEY", "fake-dashscope-key")
    overlapping = [
        {"title": "a", "reason": "r", "quote": "q", "start": 2.0, "end": 8.0},
        {"title": "b", "reason": "r", "quote": "q", "start": 3.0, "end": 9.0},
    ]
    monkeypatch.setenv("VIDEO_CUT_LLM_PROVIDER_FAKE", json.dumps(overlapping))
    _stage_transcript(tmp_path / "output", fixture_video)

    result = cli_runner.invoke(app, ["analyze", str(fixture_video), "--output-dir", str(tmp_path / "output")])

    assert result.exit_code == 0
    assert "Overlap" in result.output or "overlap" in result.output
