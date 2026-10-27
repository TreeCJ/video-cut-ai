"""Tests for millisecond-precision boundary nudging on highlight cards.

Frontend contract only: TestClient renders the detail page HTML and the
assertions check the markup + script hooks the browser-side nudge logic
hangs on. Arithmetic itself lives in JS (toBeVerifiedByPlaywright below);
here we pin the template contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from video_cut import paths
from video_cut.web import create_app

HIGHLIGHTS = [
    {
        "title": "开场反转",
        "reason": "前30秒抛出反常识结论",
        "quote": "其实90%的人都搞错了。",
        "start": 2.5,
        "end": 5.0,
    },
]


@pytest.fixture()
def studio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """An app whose single video already has highlights.json on disk."""
    monkeypatch.chdir(tmp_path)  # isolate from any real .env in the repo root

    output_dir = tmp_path / "output"
    video = tmp_path / "fixture.mp4"
    video.write_bytes(b"fake")
    stem = video.stem

    target_dir = output_dir / stem
    target_dir.mkdir(parents=True)
    (target_dir / paths.WEB_SESSION_FILE_NAME).write_text(
        json.dumps({"source_path": str(video)}, ensure_ascii=False),
        encoding="utf-8",
    )
    (target_dir / paths.HIGHLIGHTS_FILE_NAME).write_text(
        json.dumps(HIGHLIGHTS, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "output_dir": output_dir,
        "stem": stem,
        "target_dir": target_dir,
    }


@pytest.fixture()
def client(studio: dict[str, Path]) -> TestClient:
    return TestClient(create_app(studio["output_dir"]))


def test_cards_render_nudge_steppers_with_ms_precision(
    client: TestClient, studio: dict[str, Path]
) -> None:
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    html = response.text
    # Stepper buttons flank each boundary label (start and end).
    assert html.count('class="nudge dec"') >= 2 * len(HIGHLIGHTS)
    assert html.count('class="nudge inc"') >= 2 * len(HIGHLIGHTS)
    # Buttons carry the boundary they nudge.
    assert 'data-bound="start"' in html
    assert 'data-bound="end"' in html
    # Time labels show millisecond precision.
    assert "2.500s" in html
    assert "5.000s" in html


def test_sliders_use_millisecond_step(
    client: TestClient, studio: dict[str, Path]
) -> None:
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    html = response.text
    assert 'step="0.001"' in html
    assert 'step="0.1"' not in html


def test_script_carries_nudge_step_and_modifier_semantics(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """The inline script must define the step ladder and modifier routing."""
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    script = response.text
    # Default 10ms step; Shift 100ms; Alt 1ms; labels 3 decimals.
    # Slice the inline script that carries the nudge logic (the page has
    # other scripts — e.g. the filmstrip's toFixed(1) — that are not ours).
    k = script.index("NUDGE_STEP_MS")
    cards_script = script[script.rindex("<script>", 0, k):script.index("</script>", k)]
    assert "NUDGE_STEP_MS" in cards_script
    assert "return 0.1" in cards_script  # Shift ladder rung
    assert "toFixed(3)" in cards_script
    assert "toFixed(1)" not in cards_script
    # Keydown wiring: document-level preview handler + slider handler +
    # stepper-button handler (arrow keys work when a stepper has focus).
    assert cards_script.count('addEventListener("keydown"') >= 3
