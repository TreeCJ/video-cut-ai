# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent skills

### Issue tracker

Issues live as markdown files under `.scratch/<feature>/` in this repo. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## 常用命令

```bash
uv run pytest                              # 全量测试
uv run pytest tests/test_analyze.py        # 单文件
uv run pytest tests/test_analyze.py::test_analyze_writes_highlights_json_matching_the_contract  # 单条测试
uv run video-cut --help                    # CLI 入口
uv run video-cut serve > /tmp/video-cut-serve.log 2>&1 &   # Web 工作台：http://127.0.0.1:8462（默认热重载），日志固定路径便于 tail
```

cut 步骤会调用 ffmpeg，需要本机已安装且在 PATH 中。

`serve` 默认端口 8462、`--reload` 默认开（改 `src/` 下代码自动重启；`--no-reload` 关闭，此时 `--output-dir` 才生效——reload 模式固定用 `output` 目录）。

## 架构

流水线由四个 CLI 命令组成（`cli.py`，typer）：`extract-audio` → `transcribe` → `analyze` → `cut`；`run` 把它们串起来。产物落在 `output/<视频名>/`，每步发现产物已存在就跳过，除非加 `--force`。

跨文件的关键机制：

- **工件链 + 文件名集中管理**：每一步读上一步的产物（`audio.m4a` → `transcript.json` → `highlights.json` → `clips/` + `merged.mp4`）。文件名统一在 `paths.py`——不要硬编码。
- **Quote 锚点时间对齐**（`align.py`）：LLM 给的 start/end 只是提示。每个 Highlight 带一条逐字复制的 `quote`；cut 时拿它模糊匹配转录句子，把时间戳重新锚定到转录上——转录是时间判断的唯一事实来源。磁盘上的 highlights.json 永不被修改，对齐只在切的时候在内存中发生。
- **契约校验集中**（`cutting.py` 的 `Highlight.from_dict`）：五字段契约（title/reason/quote/start/end）统一在这里校验，LLM 结果解析和 highlights.json 加载都走它。
- **分段统一编码**（`cutting.py`）：每个片段用完全相同的参数重编码（libx264、CFR 30fps、≤1080p、AAC 48kHz 立体声），这样 `merge_segments` 才能用 concat demuxer + stream copy 拼接，合并不重编码。
- **配置**（`config.py`）：所有环境变量带 `VIDEO_CUT_` 前缀，隔离 shell 环境污染。`.env` 和进程环境合并；必需键进程环境优先，模型覆盖走 `_resolve_model` 解析。
- **Provider/Engine 协议缝**：`llm/__init__.py`（Provider）和 `asr/__init__.py`（Engine）是协议抽象。默认实现分别是 Qwen（DashScope OpenAI 兼容端点）和 Paraformer。

## 测试

测试通过环境变量替换网络依赖，绝不触网：

- `VIDEO_CUT_LLM_PROVIDER_FAKE`——预置 JSON 高光列表，或 `{"raw_text": "..."}` 把畸形 LLM 回复原样送进真实解析器。
- `VIDEO_CUT_ASR_ENGINE_FAKE`——预置转录载荷。
- `VIDEO_CUT_OSS_FAKE_DIR`——本地目录冒充 OSS；删除操作记录在 `<dir>/deleted.json`。
- `_VIDEO_CUT_FAKE_PROVIDER_CALLS_FILE` / `_VIDEO_CUT_FAKE_PROVIDER_MODEL_FILE`——观测点，断言 CLI 传给 provider 的参数。

fixture 里必须洗掉真实云配置（参考 `test_analyze.py` 的 `fake_llm`：删 `VIDEO_CUT_DASHSCOPE_API_KEY`，并 chdir 到 `tmp_path` 隔离仓库根的 `.env`）。

## 领域语言

`GLOSSARY.md` 定义统一语言（Transcript、Sentence、Word、Highlight、Quote、Clip、Segment、Merged、Provider、Engine）。Highlight 构成叙事序列而非孤立瞬间——合并成品应能复述整个故事情节。代码与术语表保持同步：术语含义变化时，在同一个改动里更新术语表。
