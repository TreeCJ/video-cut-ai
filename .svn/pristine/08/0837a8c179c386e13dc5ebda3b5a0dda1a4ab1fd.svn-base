# Paraformer Real-time v2 使用指南

## 概述

已成功集成阿里云 `paraformer-realtime-v2` 模型，该模型支持**实时流式识别**，可以直接处理本地音频文件，**无需OSS存储**。

## 优势

✅ **无需OSS**: 直接读取本地音频文件
✅ **实时流式**: WebSocket连接，边录边传
✅ **更低延迟**: 相比异步任务模式更快
✅ **节省成本**: 无OSS存储和流量费用
✅ **开发友好**: 适合本地开发和测试

## 配置

### `.env` 文件

```bash
# DashScope API Key（必需）
VIDEO_CUT_DASHSCOPE_API_KEY=sk-7efc7735d4864c12bdd22c397873ea9b

# 使用实时模型
VIDEO_CUT_ASR_MODEL=paraformer-realtime-v2

# 其他配置（可选）
VIDEO_CUT_LLM_MODEL=qwen-max
```

**注意**: 不再需要配置OSS相关参数！

## 安装依赖

```bash
# dashscope SDK已包含在项目中
# 如需重新安装：
pip install dashscope
```

## 使用方法

### 1. 命令行方式

```bash
# 提取音频
uv run video-cut extract-audio input.mp4

# 转录音频（自动使用实时引擎）
uv run video-cut transcribe input.mp4

# 一键完成全流程
uv run video-cut run input.mp4 --auto
```

### 2. Web服务方式

```bash
# 启动Web服务
uv run video-cut serve

# 访问 http://127.0.0.1:8462
# 在浏览器中操作完整流水线
```

### 3. Python脚本测试

```bash
# 运行测试脚本
python test_realtime_asr.py
```

## 技术实现

### 核心架构

```
本地音频文件
    ↓
读取分片 (100ms/chunk)
    ↓
WebSocket流式传输
    ↓
DashScope API (paraformer-realtime-v2)
    ↓
实时返回识别结果
    ↓
构建Transcript对象
```

### 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| model | paraformer-realtime-v2 | 实时识别模型 |
| sample_rate | 16000 Hz | 音频采样率 |
| format | wav/mp3等 | 音频格式 |
| language_hints | ["zh", "en"] | 语言提示 |
| chunk_size | 3200 bytes | 每块大小 (~100ms) |

### 支持的音频格式

- WAV (推荐，需16kHz mono)
- MP3
- PCM
- OPUS
- AAC
- M4A

### 文件格式要求

**WAV文件**:
- 采样率: 16kHz
- 声道: 单声道 (mono)
- 位深: 16-bit

**其他格式**: 自动处理

## 工作流程示例

### 完整流程

```bash
# 1. 准备视频文件
input.mp4

# 2. 提取音频 (生成 audio.m4a)
uv run video-cut extract-audio input.mp4

# 3. 转录 (使用实时引擎，无需OSS)
uv run video-cut transcribe input.mp4
# 输出: output/input/transcript.json

# 4. 分析挑片段
uv run video-cut analyze input.mp4
# 输出: output/input/highlights.json

# 5. 切片合并
uv run video-cut cut input.mp4
# 输出: output/input/clips/*.mp4 和 merged.mp4
```

### 一键完成

```bash
uv run video-cut run input.mp4 --auto
```

## 故障排除

### 问题1: API Key 403错误

**症状**: `403 Forbidden`

**原因**:
- API Key无效或过期
- 账号未开通百炼服务

**解决**:
1. 登录 https://bailian.console.aliyun.com/
2. 检查API Key状态
3. 确认已开通百炼服务
4. 必要时重新生成Key

### 问题2: 音频格式不支持

**症状**: `ValueError: Expected sample rate 16000, got 44100`

**解决**: 音频会自动转换为16kHz mono，确保extract-audio步骤正常执行

### 问题3: WebSocket连接失败

**症状**: 连接超时或无法建立

**解决**:
1. 检查网络连接
2. 确认防火墙允许WebSocket
3. 验证endpoint地址正确

### 问题4: ImportError

**症状**: `ImportError: dashscope package is required`

**解决**:
```bash
pip install dashscope
```

## 性能对比

| 特性 | paraformer-v2 | paraformer-realtime-v2 |
|------|---------------|------------------------|
| 识别方式 | 异步任务 | 实时流式 |
| 需要OSS | ✅ 是 | ❌ 否 |
| 延迟 | 较高(轮询) | 较低(实时) |
| 成本 | OSS费用 + API | 仅API |
| 适用场景 | 批量处理 | 开发/实时应用 |

## 代码示例

### 直接使用引擎

```python
from video_cut.asr.paraformer_realtime import ParaformerRealtimeEngine

# 创建引擎
engine = ParaformerRealtimeEngine(
    api_key="your-api-key",
    model="paraformer-realtime-v2"
)

# 转录音频
transcript = engine.transcribe("audio.wav")

# 查看结果
for sentence in transcript.sentences:
    print(f"[{sentence.begin_time:.2f}s-{sentence.end_time:.2f}s] {sentence.text}")
```

### 在CLI中使用

系统会自动根据 `VIDEO_CUT_ASR_MODEL` 配置选择对应的引擎：

```python
# cli.py 中的 _build_engine() 函数
if "realtime" in asr_model:
    return ParaformerRealtimeEngine(...)
else:
    return ParaformerEngine(...)
```

## 相关文件

- 实时引擎: `src/video_cut/asr/paraformer_realtime.py`
- 传统引擎: `src/video_cut/asr/paraformer.py`
- CLI入口: `src/video_cut/cli.py`
- 配置文件: `.env`
- 测试脚本: `test_realtime_asr.py`

## 总结

✅ **已完成**: paraformer-realtime-v2 引擎集成
✅ **无需OSS**: 直接处理本地音频文件
✅ **自动切换**: 根据配置自动选择引擎
✅ **向后兼容**: 保留原有paraformer-v2支持

现在你可以完全在没有OSS配置的情况下使用视频转录功能了！🎉
