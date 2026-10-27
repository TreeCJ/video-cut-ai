"""Tests for per-card preview: markup the playback JS binds to.

The playback itself (seek the source video, auto-pause at end, I/O hotkeys
writing the current position via the boundaries endpoint) is frontend
behavior; the HTTP seam asserts the data layer: every card carries
data-start/data-end with the current draft values and a preview control,
and after a boundary edit the re-rendered cards carry the new values so
the next preview uses the new range without a re-encode.
"""

from __future__ import annotations

import json
import re
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
    {
        "title": "中段论证",
        "reason": "信息密度最高的一段",
        "quote": "今天我们把这个问题讲透。",
        "start": 10.0,
        "end": 13.5,
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
    client = TestClient(create_app(studio["output_dir"]))
    response = client.get(f"/videos/{studio['stem']}")
    assert response.status_code == 200
    return client


def _card_html(html: str, index: int) -> str:
    """Extract one card's markup by its stable element id."""
    match = re.search(
        rf'<li[^>]*id="highlight-card-{index}"[^>]*>.*?</li>',
        html,
        re.DOTALL,
    )
    assert match, f"card {index} not found in page"
    return match.group(0)


def test_cards_carry_draft_boundaries_as_data_attributes(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """Each card exposes data-start/data-end so the preview JS reads the
    current draft range straight from the DOM (no extra round-trip)."""
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    first = _card_html(response.text, 0)
    second = _card_html(response.text, 1)
    assert 'data-start="2.5"' in first
    assert 'data-end="5.0"' in first
    assert 'data-start="10.0"' in second
    assert 'data-end="13.5"' in second


def test_cards_render_a_preview_control(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """Each card has a preview button the JS binds seek-play to."""
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    html = response.text
    assert html.count('class="preview"') >= len(HIGHLIGHTS)


def test_preview_page_wires_hotkey_hint(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """The card markup advertises the I/O hotkeys so the binding is
    discoverable and the JS hook point exists."""
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    assert "preview-hotkeys" in response.text


def test_boundary_edit_rerenders_card_with_new_data_attributes(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """After I/O 打点 (or any boundary write) the swapped card carries the
    new range in its data attributes — the next preview plays the new range."""
    response = client.post(
        f"/videos/{studio['stem']}/highlights/0/boundaries",
        data={"start": "3.25", "end": "4.75"},
    )

    assert response.status_code == 200
    card = _card_html(response.text, 0)
    assert 'data-start="3.25"' in card
    assert 'data-end="4.75"' in card
    assert 'class="preview"' in card

    draft = json.loads(
        (studio["target_dir"] / paths.HIGHLIGHTS_DRAFT_FILE_NAME).read_text(
            encoding="utf-8"
        )
    )
    assert draft[0]["start"] == 3.25
    assert draft[0]["end"] == 4.75
    assert draft[0]["locked"] is True
