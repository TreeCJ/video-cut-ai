"""Tests for draft editing endpoints: boundaries, delete, reorder.

HTTP seam only: each POST rewrites the whole draft file; the detail page
re-GET reflects the edit; the original highlights.json (content and mtime)
is never touched by any edit endpoint. Manually changed boundaries set
locked=true and the card renders a lock badge.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from video_cut import paths
from video_cut.web import create_app

# 一张卡的两条滑杆（DOM 顺序：slider-start 在前，slider-end 在后）。
SLIDER_PATTERN = re.compile(
    r'class="slider-(start|end)"[^>]*?min="([^"]+)"[^>]*?max="([^"]+)"'
)


def _slider_scales(html: str) -> list[tuple[str, str, str]]:
    """(name, min, max) 三元组，按 DOM 顺序。"""
    return SLIDER_PATTERN.findall(html)


def _assert_common_scale(html: str, expected_cards: int) -> None:
    """同一张卡的 IN/OUT 滑杆必须共用同一刻度（同 min 同 max）。"""
    scales = _slider_scales(html)
    assert len(scales) == 2 * expected_cards
    for i in range(0, len(scales), 2):
        name_start, min_start, max_start = scales[i]
        name_end, min_end, max_end = scales[i + 1]
        assert name_start == "start"
        assert name_end == "end"
        assert min_start == min_end, "IN/OUT 滑杆刻度不同"
        assert max_start == max_end, "IN/OUT 滑杆刻度不同"

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
    client = TestClient(create_app(studio["output_dir"]))
    # First view generates the draft from highlights.json.
    response = client.get(f"/videos/{studio['stem']}")
    assert response.status_code == 200
    return client


def _draft_path(studio: dict[str, Path]) -> Path:
    return studio["target_dir"] / paths.HIGHLIGHTS_DRAFT_FILE_NAME


def _read_draft(studio: dict[str, Path]) -> list[dict]:
    return json.loads(_draft_path(studio).read_text(encoding="utf-8"))


def _assert_highlights_untouched(
    studio: dict[str, Path], content: str, mtime: float
) -> None:
    highlights_path = studio["highlights_path"]
    assert highlights_path.read_text(encoding="utf-8") == content
    assert highlights_path.stat().st_mtime == mtime


def test_boundary_update_rewrites_draft_and_locks_the_item(
    client: TestClient, studio: dict[str, Path]
) -> None:
    original_content = studio["highlights_path"].read_text(encoding="utf-8")
    original_mtime = studio["highlights_path"].stat().st_mtime

    response = client.post(
        f"/videos/{studio['stem']}/highlights/1/boundaries",
        data={"start": "11.0", "end": "14.5"},
    )

    assert response.status_code == 200
    draft = _read_draft(studio)
    assert draft[1]["start"] == 11.0
    assert draft[1]["end"] == 14.5
    assert draft[1]["locked"] is True
    # Other items untouched and still unlocked.
    assert draft[0]["locked"] is False
    assert draft[2]["locked"] is False
    assert draft[0]["start"] == 2.5
    _assert_highlights_untouched(studio, original_content, original_mtime)


def test_boundary_update_response_shows_lock_badge_and_new_duration(
    client: TestClient, studio: dict[str, Path]
) -> None:
    response = client.post(
        f"/videos/{studio['stem']}/highlights/1/boundaries",
        data={"start": "11.0", "end": "14.5"},
    )

    assert response.status_code == 200
    assert "lock-badge" in response.text
    assert "11.0" in response.text
    assert "14.5" in response.text
    assert "3.5" in response.text  # new card duration
    # Total duration: 2.5 + 3.5 + 10.0 = 16.0 -> 2.5+3.5+10.0
    assert f"{(5.0 - 2.5) + (14.5 - 11.0) + (30.0 - 20.0):.1f}" in response.text


def test_reget_reflects_boundary_update(
    client: TestClient, studio: dict[str, Path]
) -> None:
    client.post(
        f"/videos/{studio['stem']}/highlights/1/boundaries",
        data={"start": "11.0", "end": "14.5"},
    )

    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    html = response.text
    assert "11.0" in html
    assert "14.5" in html
    assert "lock-badge" in html


def test_boundary_update_rejects_inverted_range(
    client: TestClient, studio: dict[str, Path]
) -> None:
    before = _read_draft(studio)

    response = client.post(
        f"/videos/{studio['stem']}/highlights/1/boundaries",
        data={"start": "15.0", "end": "11.0"},
    )

    assert response.status_code == 422
    assert _read_draft(studio) == before


def test_delete_removes_item_from_draft(
    client: TestClient, studio: dict[str, Path]
) -> None:
    original_content = studio["highlights_path"].read_text(encoding="utf-8")
    original_mtime = studio["highlights_path"].stat().st_mtime

    response = client.post(f"/videos/{studio['stem']}/highlights/1/delete")

    assert response.status_code == 200
    draft = _read_draft(studio)
    assert len(draft) == 2
    assert [item["title"] for item in draft] == ["开场反转", "收尾承诺"]
    assert "中段论证" not in response.text
    # Deleting must not lock or alter the remaining items.
    assert all(item["locked"] is False for item in draft)
    _assert_highlights_untouched(studio, original_content, original_mtime)


def test_reget_reflects_delete(client: TestClient, studio: dict[str, Path]) -> None:
    client.post(f"/videos/{studio['stem']}/highlights/1/delete")

    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    assert "中段论证" not in response.text
    assert "开场反转" in response.text


def test_reorder_updates_draft_order(
    client: TestClient, studio: dict[str, Path]
) -> None:
    original_content = studio["highlights_path"].read_text(encoding="utf-8")
    original_mtime = studio["highlights_path"].stat().st_mtime

    response = client.post(
        f"/videos/{studio['stem']}/highlights/reorder",
        data={"order": ["2", "0", "1"]},
    )

    assert response.status_code == 200
    draft = _read_draft(studio)
    assert [item["title"] for item in draft] == [
        "收尾承诺",
        "开场反转",
        "中段论证",
    ]
    html = response.text
    assert html.index("收尾承诺") < html.index("开场反转") < html.index("中段论证")
    _assert_highlights_untouched(studio, original_content, original_mtime)


def test_reorder_rejects_permutation_that_drops_an_item(
    client: TestClient, studio: dict[str, Path]
) -> None:
    before = _read_draft(studio)

    response = client.post(
        f"/videos/{studio['stem']}/highlights/reorder",
        data={"order": ["0", "0", "1"]},
    )

    assert response.status_code == 422
    assert _read_draft(studio) == before


def test_reget_reflects_reorder(client: TestClient, studio: dict[str, Path]) -> None:
    client.post(
        f"/videos/{studio['stem']}/highlights/reorder",
        data={"order": ["2", "0", "1"]},
    )

    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    html = response.text
    assert html.index("收尾承诺") < html.index("开场反转") < html.index("中段论证")


def test_edit_endpoints_404_for_unknown_index_or_video(
    client: TestClient, studio: dict[str, Path]
) -> None:
    assert (
        client.post(
            f"/videos/{studio['stem']}/highlights/9/boundaries",
            data={"start": "1.0", "end": "2.0"},
        ).status_code
        == 404
    )
    assert (
        client.post(f"/videos/{studio['stem']}/highlights/9/delete").status_code
        == 404
    )
    assert (
        client.post(
            "/videos/nonexistent/highlights/0/boundaries",
            data={"start": "1.0", "end": "2.0"},
        ).status_code
        == 404
    )


def test_edit_endpoints_409_without_highlights(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output"
    video = tmp_path / "bare.mp4"
    video.write_bytes(b"fake")
    target_dir = output_dir / video.stem
    target_dir.mkdir(parents=True)
    (target_dir / paths.WEB_SESSION_FILE_NAME).write_text(
        json.dumps({"source_path": str(video)}, ensure_ascii=False),
        encoding="utf-8",
    )
    client = TestClient(create_app(output_dir))

    assert (
        client.post(
            f"/videos/{video.stem}/highlights/0/boundaries",
            data={"start": "1.0", "end": "2.0"},
        ).status_code
        == 409
    )
    assert (
        client.post(f"/videos/{video.stem}/highlights/0/delete").status_code
        == 409
    )
    assert (
        client.post(
            f"/videos/{video.stem}/highlights/reorder", data={"order": ["0"]}
        ).status_code
        == 409
    )


def test_card_renders_editing_controls(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """Cards expose dual range sliders, a delete button, and reorder controls."""
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    html = response.text
    assert html.count('type="range"') >= 2 * len(HIGHLIGHTS)
    assert "slider-start" in html
    assert "slider-end" in html
    assert "delete" in html
    assert "move-up" in html
    assert "move-down" in html


def test_slider_pair_shares_one_scale(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """一张卡的两条滑杆共用同一刻度：抓到左边的滑块必是 IN。

    旧实现 IN 刻度 [0,end]、OUT 刻度 [start,end*1.5+30]，屏幕位置由各自
    百分比决定，OUT 滑块可能跑到 IN 左边，且交叉改 min/max 造成"联动"
    假象。统一刻度后滑块屏幕位置 = 真实时间轴位置。
    """
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    _assert_common_scale(response.text, len(HIGHLIGHTS))


def test_slider_scale_spans_full_timeline(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """滑杆刻度 = 全时间轴 [0, 视频总长]：琥珀选段条与滑块位置一致。"""
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    html = response.text
    scales = _slider_scales(html)
    for _name, min_value, max_value in scales:
        assert float(min_value) == 0.0
        assert float(max_value) > max(h["end"] for h in HIGHLIGHTS)


def test_boundary_update_response_keeps_common_slider_scale(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """编辑端点重渲染的卡片同样共用刻度（HTMX swap 后行为不变）。"""
    response = client.post(
        f"/videos/{studio['stem']}/highlights/1/boundaries",
        data={"start": "11.0", "end": "14.5"},
    )

    assert response.status_code == 200
    _assert_common_scale(response.text, len(HIGHLIGHTS))


def test_slider_scale_identical_across_cards(
    client: TestClient, studio: dict[str, Path]
) -> None:
    """整页所有滑杆共用同一刻度：HTMX swap 后位置不漂移。"""
    response = client.get(f"/videos/{studio['stem']}")

    assert response.status_code == 200
    scales = _slider_scales(response.text)
    maxes = {max_value for _name, _min, max_value in scales}
    mins = {min_value for _name, min_value, _max in scales}
    assert len(maxes) == 1
    assert mins == {"0"}
