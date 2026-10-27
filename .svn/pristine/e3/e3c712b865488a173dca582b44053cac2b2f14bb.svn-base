# Detail 页重设计：工作台布局

## Intent

当前 `/videos/{stem}` detail 页把所有内容瀑布流堆叠：步骤大卡、源视频、转录、高光卡、剪切表单、报告、产物。高频操作（调高光边界 + 重切）需要在长页面里来回滚动找视频和卡片。重设计目标：**调边界时视频始终在视野内，一键跑流水线到高光，产物收敛到底部动作区**。

## 用户确认的决策

- 布局：视频常驻顶部 sticky + 下方工作区（高光列表为默认视图）。
- 一键全流程：`extract-audio → transcribe → analyze` 顺序跑，到 analyze 完成即停，等用户审高光；任何一步出错中断，不再继续。
- 转录默认折叠，展开后点句子仍 seek 视频。

## Goals

- 顶部 sticky 区：源视频播放器 + 压缩步骤条（横向 4 个小步，非大卡）+「一键跑到高光」按钮。
- 工作区主区：高光片段卡片列表（沿用现有卡片的滑杆/预览/I/O 打点/删除/重排交互）。
- 拖滑杆时顶部视频**实时 seek 跟随**（当前拖的是起点滑杆就 seek 起点，终点滑杆 seek 终点），不自动播放；点「预览」仍播放选中区间。
- 转录折叠在 `<details>` 里，有句子时才渲染。
- 底部动作条：「生成对齐报告」「直接剪切合并」；报告与产物（clips/merged）渲染在该区。
- 单步触发（运行/强制重跑/analyze prompt）保留，收进步骤条的每步详情展开里。

## Non-goals

- 不改后端步骤注册表、TaskRunner、SSE 协议、draft 编辑端点、cut 两段式端点的语义。
- 不改首页（视频库）。
- 不做拖拽排序（保留上移/下移按钮）。
- 不做响应式移动端专项适配（桌面优先，但不要横向滚动破坏）。

## Anti-goals

- 不要为布局引入前端框架或构建步骤（保持 Jinja + HTMX + 原生 JS）。
- 不要把高光卡改成 tab 或弹窗——卡片列表就是主工作区。
- 一键跑不要在 analyze 之后自动 cut。

## 实现要点（builder 须知）

### 一键跑端点

新增 `POST /videos/{stem}/run-to-highlights`：服务端在一个后台任务里顺序执行 extract-audio → transcribe → analyze 三个 work（复用 `STEP_REGISTRY` 的 `build_work`，`force=False`，skip 语义不变），任一失败即抛异常中断。任务经 `runner.try_start(stem, "run-to-highlights", work)` 走单任务锁。SSE 里这条任务的 `step` 字段是 `run-to-highlights`；前端步骤条的状态仍从 `_step_statuses`（产物存在性）推导，SSE 快照/事件里属于三步之一的任务也要刷新对应小步状态。

注意：`_step_statuses` 里 `latest_for_stem` 只取**最近一条**任务——一键跑任务的状态不对应任何单步，步骤条小步展示按产物存在性即可；一键跑按钮的 busy 态用 `runner.is_busy()`。

### 模板结构（detail.html 重排）

```
<header class="sticky-top">          # position: sticky; top: 0
  <video id="source-video">          # 常驻播放器
  <ol class="step-strip">            # 4 个小步：name + status 点
    <li> + <details> 单步表单        # step_card.html 内容收进 details
  </ol>
  <button hx-post run-to-highlights> # 一键跑
</header>
<main>
  <section id="highlight-cards">     # 默认主区（无高光时显示空态提示）
  <details class="transcript">       # 折叠转录
  <section id="final-cut">           # 底部动作条：报告 + 确认 + 产物
</main>
```

- `step_card.html` 保留为单步详情（form），但外层从卡片改为 `<li><details>` 的一项；SSE 的 `renderCard` 更新逻辑改为按 `data-step` 查找小步的状态元素。
- 高光卡的实时 seek：在 `highlight_cards.html` 现有 `refresh()` 里加 `video.currentTime = <被拖滑杆的值>`（起点滑杆 seek 起点值，终点滑杆 seek 终点值），不调用 `play()`。
- 无高光且 analyze 未跑过时，主区显示引导文案（「点击上方一键跑」）。
- 无源视频时 sticky 区退化为只有步骤条 + 按钮。

### 样式

base.html 的 `<style>` 增补：`.sticky-top`（sticky + 背景色 + 底部边框）、`.step-strip`（横向 flex，小圆点状态色沿用现有 status-* 色）、`.transcript` details 样式、底部 `#final-cut` 动作区上边距分隔。不引入新配色。

### SSE 与页面刷新策略（用户已确认）

- **任务结束 = 整页 reload**。前端 SSE 收到 `task` 事件且 `task.stem === stem` 且 `status in (done/failed/skipped)` 时 `location.reload()`。一键跑完成后高光卡随 reload 出现；cut 完成后产物随 reload 出现。缺点（reload 丢弃未应用的滑杆调整）用户已接受：任务跑时按钮全禁用，调边界与跑任务天然互斥。
- **一键跑期间步骤条不实时更新**（无逐步进度事件），跑完 reload 后一次变绿。
- 删除现有 `renderCard` 单卡 DOM 更新 JS（步骤条状态全部由服务端渲染 + reload 覆盖）。
- `run-to-highlights` 任务的 SSE 事件不映射到任何小步，只触发 reload。

### cut 两段式在新布局的响应形状

- 「生成对齐报告」响应不变：`cut_report.html` swap 进底部区。
- 「确认剪切合并」202 响应**不再是步骤卡**，改为返回 `#final-cut` 区片段（含「剪切中…」提示）；任务结束 reload 后该区显示产物。`cut.py` 的 `_render_step_card` 代理随之删除。
- 报告在确认后被清除（现有语义），reload 后报告区消失、产物区出现——确认即表示报告使命完成。

## 测试

- 新端点：顺序执行、skip 语义、失败中断、任务锁 409。
- 模板：sticky 区存在且 video 在其中、转录在 details 内、高光区在无高光时显示空态、底部动作条存在。
- 实时 seek 属纯前端行为，不进 pytest；手动验收。

## 我的判断（未经用户确认的小决策）

- 一键跑失败时中断点之后的步不跑，按钮可再次点击续跑（skip 语义保证已完成步不重跑）。
- `run-to-highlights` 不进 `STEP_NAMES`/`STEP_REGISTRY`（不是流水线的一步，只是组合触发），只在 TaskRunner 层面作为一个任务存在；步骤条小步状态推导不变。
- analyze 的自定义 prompt 输入留在 analyze 小步的 details 里，一键跑不带 prompt（用 session 里已存的）。
