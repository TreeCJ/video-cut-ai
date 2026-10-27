# Detail 页工作台布局 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/videos/{stem}` detail 页从瀑布流重排为工作台布局：顶部 sticky 视频 + 压缩步骤条 + 一键跑到高光按钮；高光列表为主工作区，拖滑杆实时 seek；转录折叠；剪切动作与产物收敛底部。

**Architecture:** 后端新增一个组合端点 `POST /videos/{stem}/run-to-highlights`（单任务内顺序跑 extract-audio→transcribe→analyze，失败中断，skip 语义不变）；前端重排 `detail.html`/`step_card.html`/`base.html` 样式，复用现有 SSE、draft 编辑、cut 两段式端点，不改其语义。

**Tech Stack:** FastAPI + Jinja2 + HTMX + 原生 JS（无构建步骤）。

**Spec:** `docs/superpowers/specs/2026-10-18-detail-page-redesign-design.md`

## Global Constraints

- 流水线步骤名与注册表不变：`STEP_NAMES = ("extract-audio", "transcribe", "analyze", "cut")`；`run-to-highlights` 不进 `STEP_REGISTRY`。
- 测试不触网：沿用 `VIDEO_CUT_ASR_ENGINE_FAKE` / `VIDEO_CUT_LLM_PROVIDER_FAKE` / `VIDEO_CUT_OSS_FAKE_DIR` 环境变量 fake；fixture 洗真实云配置并 chdir 到 `tmp_path`（参照 `tests/test_web_steps.py` 的 `web_env`）。
- 单任务锁：所有重活经 `runner.try_start`，锁占用返回 409 + 「已有任务在运行，请等待完成」。
- 文件名只在 `paths.py`；契约校验只在 `cutting.py` 的 `Highlight.from_dict`。
- SSE 事件格式不变（`event: task` / `event: snapshot`，payload 字段不变）。
- 运行测试命令：`uv run pytest`（遇 `ModuleNotFoundError: tests` 用 `PYTHONPATH=. uv run pytest`）。
- Commit 信息格式：`<type>: <description>`，结尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。

## Review Focus

1. 一键跑跑到一半失败：后续步不执行，已完成步的产物保留，再次点击能续跑（skip 语义）→ Task 1 `test_run_to_highlights_stops_on_failure` + `test_run_to_highlights_resumes_after_failure`。
2. 锁占用时点击一键跑 → 409 → Task 1 `test_run_to_highlights_returns_409_when_busy`。
3. analyze 未完成（无 highlights/draft）时点底部「生成对齐报告」→ 现有 `_load_editable` 409 语义不变 → Task 2 模板重排不得动 cut 端点，由 `tests/test_web_final_cut.py` 既有用例兜底（全量跑绿即证明）。
4. 无源视频（源文件被移走）时 sticky 区不渲染 video 但步骤条/按钮仍可用 → Task 3 `test_detail_without_source_omits_video_but_keeps_strip`。
5. 无转录时折叠区不渲染 details → Task 3 `test_detail_without_transcript_omits_details`。
6. SSE 收到 `run-to-highlights` 任务事件时前端不把它映射到任何小步（纯前端，无 pytest；Task 4 的 JS 注释固定该行为，手动验收）。

---

### Task 1: `run-to-highlights` 组合端点

**Files:**
- Modify: `src/video_cut/web/steps.py`（新增组合 work 工厂）
- Modify: `src/video_cut/web/app.py`（注册路由）
- Test: `tests/test_web_run_to_highlights.py`

**Interfaces:**
- Consumes: `STEP_REGISTRY`, `StepContext`, `TaskRunner.try_start`, `TaskBusyError`（均已在 `web/steps.py`、`web/tasks.py` 存在）。
- Produces:
  - `build_run_to_highlights_work(context: StepContext) -> StepWork`（在 `web/steps.py`）：返回的 work 顺序调用 extract-audio/transcribe/analyze 三个 `build_work` 产出的 work，任一异常直接上抛中断；返回 detail 汇总三步 detail（`\n` join）。
  - 路由 `POST /videos/{stem}/run-to-highlights`：202 返回整条步骤条 HTML（`step_strip.html`）；404 未知视频；409 锁占用。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_web_run_to_highlights.py`，fixture 复用 `test_web_steps.py` 的 `web_env` 模式（复制 `CLOUD_KEYS`/`ENGINE_PAYLOAD`/`CANNED_HIGHLIGHTS`/`web_env`/`client`/`_register_video`）。需要一个真实短视频 fixture：查 `tests/` 里现有视频 fixture 的生成方式（`test_web_steps.py` 的 `test_full_chain_produces_cli_parity_artifacts` 用的是什么），照搬。

```python
def test_run_to_highlights_runs_three_steps_in_order(client, tmp_path):
    # 注册视频 → POST /videos/{stem}/run-to-highlights → 轮询 /videos/{stem}/tasks 直到 settle
    # 断言：audio.m4a、transcript.json、highlights.json 三个产物都生成
    # 断言：任务 step == "run-to-highlights"，status == "done"

def test_run_to_highlights_skips_existing_artifacts(client, tmp_path):
    # 先单步跑 extract-audio，再一键跑
    # 断言：任务 detail 含 "skipped"，且 audio.m4a mtime 未变

def test_run_to_highlights_stops_on_failure(client, tmp_path, monkeypatch):
    # 把 VIDEO_CUT_LLM_PROVIDER_FAKE 改成畸形 {"raw_text": "not json"} 让 analyze 失败
    # 断言：任务 status == "failed"；audio.m4a 与 transcript.json 存在；highlights.json 不存在

def test_run_to_highlights_resumes_after_failure(client, tmp_path, monkeypatch):
    # 先失败一次（同上），修回正常 fake，再次 POST
    # 断言：第二次 done，highlights.json 生成

def test_run_to_highlights_returns_409_when_busy(client, tmp_path):
    # 用 runner.acquire() 占锁（参照 test_web_tasks.py 现有做法）→ POST → 409
    # finally release

def test_run_to_highlights_404_for_unknown_video(client):
    # POST /videos/nope/run-to-highlights → 404
```

- [ ] **Step 2: 跑测试确认全败**

Run: `uv run pytest tests/test_web_run_to_highlights.py -x -q`
Expected: FAIL（404/405，路由不存在）

- [ ] **Step 3: 实现 `build_run_to_highlights_work` 于 `src/video_cut/web/steps.py`**

顺序执行三个已注册的 `build_work(StepContext(..., force=False, prompt=session 已存 prompt))`。prompt 来源：`load_session(target_dir).analyze_prompt or ""`（与 analyze 单步的预填语义一致；一键跑不接受表单 prompt）。三段子 work 的 detail 用 `\n` join 返回；任何异常不捕获，直接上抛让 TaskRunner 记 failed。

- [ ] **Step 4: 在 `src/video_cut/web/app.py` 注册路由**

在 `_register_video_routes` 里加 `POST /videos/{stem}/run-to-highlights`：校验 session（404）→ 构建 work → `runner.try_start(stem, "run-to-highlights", work)`（409 on `TaskBusyError`）→ 202 返回占位片段 `<div id="run-status">running</div>`。

- [ ] **Step 5: 跑测试确认全过**

Run: `uv run pytest tests/test_web_run_to_highlights.py -q`
Expected: PASS（6 条）

- [ ] **Step 6: 全量回归**

Run: `uv run pytest -q`
Expected: 全绿（既有 SSE/步骤/编辑/cut 用例不受影响）

- [ ] **Step 7: Commit**

```bash
git add src/video_cut/web/steps.py src/video_cut/web/app.py tests/test_web_run_to_highlights.py
git commit -m "feat: run-to-highlights combo endpoint"
```

---

### Task 2: 步骤条模板 `step_strip.html` + 状态推导适配

**Files:**
- Create: `src/video_cut/web/templates/step_strip.html`
- Modify: `src/video_cut/web/app.py`（`_render_step_card` 拆出步骤条渲染；`_detail_context` 不变）
- Test: `tests/test_web_step_strip.py`

**Interfaces:**
- Consumes: `StepStatus`（`app.py` 已有），`STEP_NAMES`。
- Produces:
  - `step_strip.html`：渲染 `<ol class="step-strip" id="steps" data-stem data-task-running>`，每项 `<li class="step-item" id="step-{{ step.name }}" data-step>` 含状态点 `<span class="status-dot status-{{ step.status }}">`、步名、`<details>` 内嵌原 `step_card.html` 的表单（运行/强制重跑/analyze prompt）与错误摘要。cut 步无表单（沿用现有 `step.name != "cut"` 判断）。
  - `_render_step_strip(request, templates, stem, steps, analyze_prompt, task_running) -> str`（`app.py`）：渲染整条步骤条，供触发端点 202 响应与 detail 页复用。
  - `trigger_step` 与 `run-to-highlights` 的 202 响应改为整条步骤条 HTML（`hx-target="#steps" hx-swap="outerHTML"`），前端不再用 JS 单卡更新（SSE renderCard 逻辑删除——见 Task 4）。

- [ ] **Step 1: 写失败测试**

`tests/test_web_step_strip.py`（复用 web_env fixture 模式）：

```python
def test_detail_renders_step_strip_with_four_steps(client, tmp_path):
    # GET /videos/{stem} → 200
    # 断言：html 含 'class="step-strip"'，id="step-extract-audio"/step-transcribe/step-analyze/step-cut 各一

def test_step_trigger_returns_whole_strip(client, tmp_path):
    # POST /videos/{stem}/steps/extract-audio → 202
    # 断言：响应体含 'class="step-strip"' 且 id="step-extract-audio" 项内含 status-running

def test_strip_shows_done_for_existing_artifacts(client, tmp_path):
    # 先在 output_dir/{stem} 放 audio.m4a → GET detail
    # 断言：step-extract-audio 项含 status-done，其余 status-pending

def test_strip_analyze_details_contains_prompt(client, tmp_path):
    # session 预置 analyze_prompt="找笑点" → GET detail
    # 断言：step-analyze 的 details 内 textarea 含 "找笑点"
```

- [ ] **Step 2: 跑测试确认全败**

Run: `uv run pytest tests/test_web_step_strip.py -x -q`
Expected: FAIL（无 step-strip 标记）

- [ ] **Step 3: 创建 `step_strip.html` + 改 `app.py`**

`step_strip.html` 结构如 Interfaces 所述；把 `step_card.html` 的 form 部分移入 `<details>`（`step_card.html` 改为只含 form 片段或被 step_strip include——选 include，保留 `step_card.html` 文件名但内容改成 form-only 片段）。

`app.py`：
- 新增 `_render_step_strip`。
- `trigger_step` 的 202 响应从单卡改为 `_render_step_strip(...)`，其中该步状态置 running（其余按产物存在性推导，与 `_step_statuses` 一致但强制覆盖当前步）。
- Task 1 的 `run-to-highlights` 202 响应同样改为 `_render_step_strip`（所有步状态按当前产物推导；任务锁已占，`task_running=True`）。
- `_render_step_card` 删除（`cut.py` 里的 `_render_step_card` 代理改为调 `_render_step_strip`，cut 确认后 202 也返回整条步骤条——cut 是 `STEP_NAMES` 之一，状态推导已覆盖）。

- [ ] **Step 4: 跑测试确认全过**

Run: `uv run pytest tests/test_web_step_strip.py -q`
Expected: PASS

- [ ] **Step 5: 全量回归**

Run: `uv run pytest -q`
Expected: 全绿。注意 `test_web_steps.py` / `test_web_final_cut.py` / `test_web_review_fixes.py` 可能断言了旧单卡 202 响应结构——若因响应改为整步骤条而失败，更新这些断言为检查 `class="step-strip"` 与目标步状态（测试行为不变：触发→任务跑→状态对）。

- [ ] **Step 6: Commit**

```bash
git add src/video_cut/web/templates/step_strip.html src/video_cut/web/templates/step_card.html src/video_cut/web/app.py src/video_cut/web/cut.py tests/
git commit -m "refactor: step cards collapse into compact step strip"
```

---

### Task 3: detail.html 重排为工作台布局 + base.html 样式

**Files:**
- Modify: `src/video_cut/web/templates/detail.html`
- Modify: `src/video_cut/web/templates/base.html`（`<style>` 增补）
- Modify: `src/video_cut/web/templates/cut_report.html`（swap 目标对齐）
- Test: `tests/test_web_layout.py`

**Interfaces:**
- Consumes: `step_strip.html`（Task 2），`highlight_cards.html`（不动），现有 `_detail_context` 全部字段。
- Produces: detail.html 新结构（spec「模板结构」节）：`<header class="sticky-top">`（video + step strip + 一键跑按钮）→ `<main>`（高光区 → 转录 `<details>` → 底部 `#final-cut` 动作条含报告与产物）。

- [ ] **Step 1: 写失败测试**

`tests/test_web_layout.py`（复用 web_env fixture 模式）：

```python
def test_detail_has_sticky_header_with_video_and_strip(client, tmp_path):
    # 注册真实视频 → GET detail
    # 断言：'class="sticky-top"' 存在；video#source-video 在 header 内（源码顺序：sticky-top 先于 highlight-cards/final-cut，且 video 标签在 step-strip 前）

def test_detail_run_button_present(client, tmp_path):
    # 断言：含 hx-post="/videos/{stem}/run-to-highlights" 的按钮

def test_detail_transcript_wrapped_in_details(client, tmp_path):
    # 先一键跑（或塞 transcript.json）→ GET detail
    # 断言：'<details class="transcript">' 存在且 sentence-list 在其后

def test_detail_without_transcript_omits_details(client, tmp_path):
    # 无 transcript.json → GET detail → 断言无 'class="transcript"'

def test_detail_without_source_omits_video_but_keeps_strip(client, tmp_path):
    # 注册后删除/移走源文件（或直接构造 session 指向不存在路径）→ GET detail
    # 断言：无 id="source-video"，但有 'class="step-strip"' 与一键跑按钮

def test_detail_empty_highlights_shows_guide(client, tmp_path):
    # 无 highlights → GET detail → 断言高光区含引导文案（如「一键跑」字样）

def test_detail_final_cut_section_after_highlights(client, tmp_path):
    # 有 highlights → GET detail
    # 断言源码顺序：highlight-cards 先于 final-cut
```

- [ ] **Step 2: 跑测试确认全败**

Run: `uv run pytest tests/test_web_layout.py -x -q`
Expected: FAIL

- [ ] **Step 3: 重排 `detail.html`**

按 spec 结构重排；一键跑按钮 form：`hx-post="/videos/{{ stem }}/run-to-highlights" hx-target="#steps" hx-swap="outerHTML"`；`source_available` 为 false 时不渲染 video；`sentences` 为空不渲染 `<details class="transcript">`；无 highlights 时渲染空态 `<section id="highlight-cards">` 含引导文案；`#final-cut` 区包含报告表单 + `cut_report` + artifacts（从旧 detail.html 平移，不改逻辑）；转录 timecode seek JS 保留。

- [ ] **Step 4: `base.html` 增补样式**

`.sticky-top { position: sticky; top: 0; background: var(--color-surface); border-bottom: 1px solid #ddd; z-index: 10; }`，`.step-strip` 横向 flex + `.status-dot` 圆点（复用 status-* 颜色）、`.step-item details` 内边距、`.transcript` summary 样式、`#final-cut` 顶部 `border-top` 分隔。body 的 `max-width: 56rem` 放宽到 `72rem`（工作台需要更宽）。其余不动。

- [ ] **Step 5: `cut_report.html` swap 目标对齐**

确认 cut 触发 form 的 `hx-target` 在重排后仍指向存在的元素（`#final-cut` / `#cut-report`），与现语义一致：报告渲染进 `#final-cut` 区内。若旧 detail.html 里 form target 是 `#final-cut` 而报告模板根 id 是 `cut-report`，保持现状（outerHTML 替换语义不变）。

- [ ] **Step 6: 跑测试确认全过 + 全量回归**

Run: `uv run pytest tests/test_web_layout.py -q && uv run pytest -q`
Expected: 全绿（`test_web_transcript_view.py`、`test_web_preview.py`、`test_web_skeleton.py` 等可能断言旧结构，按新结构更新断言，行为不变）

- [ ] **Step 7: Commit**

```bash
git add src/video_cut/web/templates/ tests/test_web_layout.py tests/
git commit -m "feat: workbench layout — sticky video header, collapsed transcript, bottom cut bar"
```

---

### Task 4: 前端交互——滑杆实时 seek + SSE 任务结束整页 reload

**Files:**
- Modify: `src/video_cut/web/templates/highlight_cards.html`（refresh 里加 seek）
- Modify: `src/video_cut/web/templates/detail.html`（SSE renderCard 逻辑删除，换 reload-on-settle）
- Test: 无新增 pytest（纯前端）；由 Task 3 全量回归兜底

**Interfaces:**
- Consumes: Task 2 的整步骤条 202/swap 机制；`#source-video`。
- Produces: 拖 `.slider-start` 时 `video.currentTime = start 值`；拖 `.slider-end` 时 `video.currentTime = end 值`；均不 `play()`。SSE `task` 事件 `status in (done/failed/skipped)` 且 `stem` 匹配时 `location.reload()`。

- [ ] **Step 1: `highlight_cards.html` 的滑杆 `input` 监听加 seek**

起点滑杆 seek 起点值、终点滑杆 seek 终点值（两个独立 handler 或 `refresh(slider)` 传参），不自动播放。`video` 不存在（无源视频）时跳过。

- [ ] **Step 2: detail.html SSE 逻辑替换**

删除 `renderCard` 单卡 DOM 更新整段 JS。SSE 监听简化为：收到 `task` 事件，`JSON.parse` 后 `task.stem === stem && ["done","failed","skipped"].includes(task.status)` → `location.reload()`。注释说明：`run-to-highlights` 事件的 step 不匹配任何小步，仅触发 reload；步骤条状态由服务端渲染 + reload 覆盖。

- [ ] **Step 3: 全量回归**

Run: `uv run pytest -q`
Expected: 全绿

- [ ] **Step 4: 手动验收清单（写进 commit body）**

- 拖滑杆视频跟随 seek 且不播放
- 一键跑/单步/cut 任务结束后页面自动 reload，步骤条变绿、高光卡/产物出现
- analyze 完成后转录折叠可见
- 报告/剪切/产物在底部

- [ ] **Step 5: Commit**

```bash
git add src/video_cut/web/templates/highlight_cards.html src/video_cut/web/templates/detail.html
git commit -m "feat: slider drag seeks video live; page reloads on task settle"
```

---

### Task 5: 文档与收尾

**Files:**
- Modify: `GLOSSARY.md`（若引入新术语——没有则跳过）
- Create: `.scratch/video-cut/issues/08-detail-workbench-layout.md`（ticket 记录）

- [ ] **Step 1: 检查 GLOSSARY.md 是否需要更新**

本次没有引入新的领域术语（run-to-highlights 是组合触发而非新概念），预期不改。确认后跳过。

- [ ] **Step 2: 写 ticket**

`.scratch/video-cut/issues/08-detail-workbench-layout.md` 记录本次改动要点与验收，沿用现有 issue 文件格式（参考 `07-web-ui-08-final-cut.md`）。

- [ ] **Step 3: 全量测试 + Commit**

```bash
uv run pytest -q
git add .scratch/video-cut/issues/08-detail-workbench-layout.md
git commit -m "docs: ticket 08 — detail workbench layout"
```
