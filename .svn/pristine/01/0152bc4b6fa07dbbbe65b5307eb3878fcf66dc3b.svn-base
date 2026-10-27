# video-cut

从长视频中提取高光片段并在本地合并成精简合集。

流水线：`extract-audio` → `transcribe` → `analyze` → `cut`，或用 `run` 一把跑完。

## 快速开始（环境安装）

需要三样东西：**Python ≥ 3.12**、**uv**（Python 包管理器）、**ffmpeg**（切音频/视频用，必须在 PATH 中）。

### macOS

```bash
# 1. uv（官方安装脚本）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. ffmpeg（Homebrew；没有 Homebrew 先装 brew.sh）
brew install ffmpeg

# 3. 验证
uv --version && ffmpeg -version | head -1
```

### Windows

```powershell
# 1. uv（官方安装脚本）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. ffmpeg（winget；装完必须手动加 PATH，见下）
winget install --id Gyan.FFmpeg

# 3. 加 PATH（winget 装到 %LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\...，
#    把包含 ffmpeg.exe 的 bin 目录加进系统 PATH，然后重开终端）
#    或手动：系统设置 → 环境变量 → Path → 新建 → 填 ffmpeg 的 bin 目录路径

# 4. 验证（重开 PowerShell 后）
uv --version
ffmpeg -version
```

ffmpeg 不在 PATH 时，`extract-audio`/`cut` 会直接报 `FileNotFoundError`/`ffmpeg not found`。

### 两种系统通用

```bash
# 克隆后进目录，同步依赖（含 pytest 等 dev 依赖）
uv sync --extra dev

# 自检：跑测试（178 条，全部离线，不触网、不需要 .env）
uv run pytest

# CLI 入口验证
uv run video-cut --help
```

日常用 `uv run video-cut <命令>`；嫌长可以先 `uv tool install --editable .` 装成全局 `video-cut` 命令。

## 配置（阿里云账号申请）

需要 `.env`（根目录，模板见 `.env.example`；或环境变量，全部 `VIDEO_CUT_` 前缀）。两处申请：

1. **DashScope API Key**（ASR + LLM 共用）：
   阿里云百炼控制台 https://bailian.console.aliyun.com/ → API-KEY 管理 → 创建。注意账号需开通百炼服务。

2. **OSS**（音频上传中转，ASR 要读公网 URL）：
   - OSS 控制台 https://oss.console.aliyun.com/ 创建 bucket（存储类型标准/低频都行）
   - RAM 控制台创建子账号，授予该 bucket 的 `oss:PutObject`、`oss:GetObject`、`oss:DeleteObject` 权限（用 ACL 或自定义策略限定到该 bucket）
   - 生成该子账号的 AccessKey ID / Secret
   - endpoint 用 bucket 所在 region 的**公网**地址，如 `https://oss-cn-hangzhou.aliyuncs.com`（必须 https——DashScope 拒绝拉取纯 http URL）

```bash
# .env 内容
# ASR + LLM（阿里云 DashScope/百炼）
VIDEO_CUT_DASHSCOPE_API_KEY=...
# OSS（音频中转）
VIDEO_CUT_OSS_BUCKET=...
VIDEO_CUT_OSS_ENDPOINT=https://oss-cn-<region>.aliyuncs.com
VIDEO_CUT_OSS_ACCESS_KEY_ID=...
VIDEO_CUT_OSS_ACCESS_KEY_SECRET=...
# LLM 模型（可选，默认 qwen-plus）
VIDEO_CUT_LLM_MODEL=qwen-plus
```

配置缺失时命令启动即报错并指明缺哪些 key，不会半路挂掉。

## 常用命令

### 一把跑完（推荐）

```bash
# 全流程，analyze 后暂停，人工审核 highlights.json 再手动切
video-cut run input.mp4

# 全自动，直接出 clips/ 和 merged.mp4
video-cut run input.mp4 --auto

# 带解说方向 + 自定义时长上限（默认 300 秒）
video-cut run input.mp4 --auto -p "只保留反转情节" --max-duration 240
```

### 分步执行

```bash
video-cut extract-audio input.mp4        # 抽出 16kHz 单声道 m4a
video-cut transcribe input.mp4           # ASR → transcript.json
video-cut analyze input.mp4              # LLM 挑片段 → highlights.json
video-cut cut input.mp4                  # 按 highlights.json 切片并合并
```

### Web 工作台

```bash
video-cut serve                # http://127.0.0.1:8462，默认热重载
```

浏览器里跑完整流水线：输入本机视频路径，抽音、转录、挑高光，卡片上直接调 IN/OUT 边界、预览、增删排序，一键切片合并。改 `src/` 下代码自动重启，无需手动重启服务。

Windows 下建议日志落文件（PowerShell 语法）：

```powershell
uv run video-cut serve *> serve.log
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--port` | 监听端口（127.0.0.1） | `8462` |
| `--output-dir` / `-o` | 输出根目录。仅 `--no-reload` 模式生效（热重载固定用 `output`） | `output` |
| `--reload` / `--no-reload` | 热重载开关 | 开 |

## 参数详解

所有命令的第一个参数都是 `video`：输入视频文件路径（必填）。

### extract-audio

从视频中抽出 16kHz 单声道 m4a 音频，供 ASR 使用。

| 参数 | 说明 | 默认 |
|------|------|------|
| `--output-dir` / `-o` | 输出根目录，产物落在 `<dir>/<视频名>/` | `output` |
| `--force` | 已有 `audio.m4a` 也强制重跑 | 关 |

### transcribe

调用 ASR 引擎（默认阿里云 Paraformer）把音频转成带时间戳的转录，产出 `transcript.json`。音频文件会先上传到配置的 OSS，再把签名 URL 交给 ASR。

| 参数 | 说明 | 默认 |
|------|------|------|
| `--output-dir` / `-o` | 输出根目录 | `output` |
| `--force` | 已有 `transcript.json` 也强制重跑 | 关 |

### analyze

调用 LLM 从转录中挑出一组能连成完整故事的片段序列，产出 `highlights.json`（可人工编辑后再切）。

| 参数 | 说明 | 默认 |
|------|------|------|
| `--output-dir` / `-o` | 输出根目录 | `output` |
| `--prompt` / `-p` | 附加挑选要求，叠加在内置叙事标准之上（如"突出人物冲突"） | 空 |
| `--count` | 最多切几段。只是上限——段数由内容决定，情节简单会自动少切 | `15` |
| `--max-duration` | 所有片段总时长上限（秒），即合并视频的目标长度。LLM 超预算时程序会从尾部丢段（首段永远保留）并打印警告 | `300.0` |
| `--force` | 已有 `highlights.json` 也强制重跑 | 关 |

挑选标准：片段按情节推进选取（起因→发展→转折→高潮→结局），相邻片段内容承接；单段 15~60 秒，时间升序输出，互不重叠。总时长超限时优先保主线关键节点。

### cut

按 `highlights.json` 切片并合并成 `merged.mp4`。

切片前会做 quote 锚点对齐：用每段的原文引用模糊匹配转录句子，把时间戳校正到真实句子位置（LLM 给的时间只是提示）。边界两侧各加缓冲，缓冲大小自适应——与邻句的间隙不足时按比例收缩，避免吃进别人的话。

每个片段统一重编码（libx264、30fps、≤1080p、AAC 48kHz），因此合并不再重编码（stream copy），速度快且无质量损失。

| 参数 | 说明 | 默认 |
|------|------|------|
| `--output-dir` / `-o` | 输出根目录 | `output` |
| `--force` | 已有 `clips/` 和 `merged.mp4` 也强制重切（会先删除旧 clips） | 关 |
| `--concurrency` | 并行切片任务数 | CPU 核数 |

没有 `transcript.json` 时会打印警告，直接使用 LLM 原始时间戳（不做对齐）。

### run

串行执行以上四步。参数是各步骤参数的超集：

| 参数 | 说明 | 默认 |
|------|------|------|
| `--output-dir` / `-o` | 输出根目录 | `output` |
| `--auto` | 全自动跑到底。不加时 analyze 后暂停，打印片段清单，等你审核/编辑 `highlights.json` 后手动跑 `cut` | 关 |
| `--force` | 全链路强制重跑 | 关 |
| `--prompt` / `-p` | 附加挑选要求（传给 analyze） | 空 |
| `--count` | 最多切几段（传给 analyze） | `15` |
| `--max-duration` | 合并视频总时长上限，秒（传给 analyze） | `300.0` |
| `--concurrency` | 并行切片任务数（传给 cut） | CPU 核数 |

### 典型工作流

```bash
# 1. 跑分析，停下来看结果
video-cut run input.mp4 -p "突出人物冲突"

# 2. 编辑 output/input/highlights.json（删段、改时间都行）

# 3. 切片合并
video-cut cut input.mp4
```

产物都在 `output/<视频名>/` 下：`audio.m4a`、`transcript.json`、`highlights.json`、`clips/*.mp4`、`merged.mp4`。

## 开发

```bash
uv run pytest          # 测试
```

### 项目结构速览

```
src/video_cut/
├── cli.py           # typer CLI 入口：extract-audio/transcribe/analyze/cut/run/serve
├── config.py        # .env + 环境变量加载（全部 VIDEO_CUT_ 前缀）
├── audio.py         # ffmpeg 抽 16kHz 单声道音频
├── transcribe.py    # ASR 调用（默认阿里云 Paraformer）
├── llm/             # LLM Provider 协议 + Qwen 实现 + 高光解析
├── asr/             # ASR Engine 协议 + Paraformer 实现
├── align.py         # quote 锚点时间对齐（转录是时间唯一事实来源）
├── cutting.py       # 切片重编码 + concat 合并、Highlight 契约校验
├── paths.py         # 产物文件名集中管理（不要散落硬编码）
└── web/             # FastAPI + HTMX Web 工作台（serve 命令）
```

领域术语见 `GLOSSARY.md`；架构决策记录见 `docs/adr/`；agent 协作约定见 `docs/agents/`。

### 常见故障

| 症状 | 原因 / 解法 |
|------|-------------|
| `ffmpeg: command not found` 或 `FileNotFoundError: 'ffmpeg'` | ffmpeg 不在 PATH。macOS：`brew install ffmpeg`；Windows：winget 装完手动加 PATH（见上文）后重开终端 |
| 8462 端口被占 | 已有 serve 在跑：浏览器直接开 http://127.0.0.1:8462，或先杀掉旧进程（macOS `lsof -ti:8462 \| xargs kill`；Windows `netstat -ano \| findstr 8462` 找 PID 后 `taskkill /PID <pid> /F`） |
| OSS 403 / AccessDenied | AccessKey 权限不够，或 bucket 策略没放开。用 RAM 子账号给足 PutObject/GetObject/DeleteObject |
| ASR 报无法下载音频 URL | OSS endpoint 必须是 https 公网地址；内网 endpoint DashScope 拉不到 |
| `ModuleNotFoundError: No module named 'tests'` | 已修复（pytest pythonpath 配置）；若仍出现说明在老分支，更新到最新 main |
| 8462 有进程但页面转圈 | 热重载卡在浏览器挂起的长连接上。杀掉进程重启 serve 即可 |
