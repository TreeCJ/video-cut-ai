"""Tests for the highlight draft lifecycle and card list rendering.

HTTP seam only: TestClient drives the app in-process. Draft generation,
draft reading, and total-duration display are all asserted through the
detail page HTML plus the draft file on disk; the original highlights.json
must never be touched by the web layer.
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
    {
        "title": "中段论证",
        "reason": "信息密度最高的一段",
        "quote": "今天我们把这个问题讲透。",
        "start": 10.0,
        "end": 13.5,
    },
    {
        "title": "收尾承诺",
        "reason": "预告全片价值",
        "quote": "记得关注下期。",
        "start": 20.0,
        "end": 30.0,
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
    highlights_path = target_dir / paths.HIGHLIGHTS_FILE_NAME
    highlights_path.write_text(
        json.dumps(HIGHLIGHTS, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "output_dir": output_dir,
        "stem": stem,
        "target_dir": target_dir,
        "highlights_path": highlights_path,
    }


@pytest.fixture()
def client(studio: dict[str, Path]) -> TestClient:
    return TestClient(create_app(studio["output_dir"]))


def _draft_path(studio: dict[str, Path]) -> Path:
    return studio["target_dir"] / paths.HIGHLIGHTS_DRAFT_FILE_NAME


def test_detail_page_renders_highlight_cards_in_time_order(
    client: TestClient, studio: dict[str, Path]
) -> None:
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    html = response.text
    for highlight in HIGHLIGHTS:
        assert highlight["title"] in html
        assert highlight["reason"] in html
    first = html.index("开场反转")
    second = html.index("中段论证")
    third = html.index("收尾承诺")
    assert first < second < third


def test_first_view_generates_draft_from_highlights_with_all_unlocked(
    client: TestClient, studio: dict[str, Path]
) -> None:
    draft_path = _draft_path(studio)
    assert not draft_path.exists()

    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    assert draft_path.exists()
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    assert len(draft) == len(HIGHLIGHTS)
    for original, drafted in zip(HIGHLIGHTS, draft):
        for field in ("title", "reason", "quote", "start", "end"):
            assert drafted[field] == original[field]
        assert drafted["locked"] is False


def test_second_view_reads_draft_not_highlights_json(
    client: TestClient, studio: dict[str, Path]
) -> None:
    client.get(f"/videos/{studio['stem']}")
    draft_path = _draft_path(studio)
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft[0]["title"] = "手工改过的标题"
    draft_path.write_text(
        json.dumps(draft, ensure_ascii=False), encoding="utf-8"
    )

    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    assert "手工改过的标题" in response.text
    original = json.loads(
        studio["highlights_path"].read_text(encoding="utf-8")
    )
    assert original == HIGHLIGHTS


def test_total_duration_is_shown_against_the_default_budget(
    client: TestClient, studio: dict[str, Path]
) -> None:
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    total = sum(h["end"] - h["start"] for h in HIGHLIGHTS)  # 16.0
    assert f"{total:.1f}" in response.text
    assert "300" in response.text


def test_existing_draft_survives_analyze_force_rerun(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """A regenerated highlights.json must not clobber an existing draft."""
    client.get(f"/videos/{studio['stem']}")
    draft_path = _draft_path(studio)
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft[0]["title"] = "手工改过的标题"
    draft_path.write_text(
        json.dumps(draft, ensure_ascii=False), encoding="utf-8"
    )

    # Simulate analyze force re-run: highlights.json is rewritten underneath.
    studio["highlights_path"].write_text(
        json.dumps(
            [
                {
                    "title": "新挑的高光",
                    "reason": "重跑产物",
                    "quote": "新引用。",
                    "start": 1.0,
                    "end": 4.0,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    assert "手工改过的标题" in response.text
    assert "新挑的高光" not in response.text
    surviving = json.loads(draft_path.read_text(encoding="utf-8"))
    assert surviving[0]["title"] == "手工改过的标题"


def test_each_card_shows_its_own_duration(
    client: TestClient, studio: dict[str, Path]
) -> None:
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    for highlight in HIGHLIGHTS:
        duration = highlight["end"] - highlight["start"]
        assert f"{duration:.1f}" in response.text
