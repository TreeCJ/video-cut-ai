# 快速开始 - Paraformer Real-time v2

## ✅ 已完成配置

你的项目已配置好使用 `paraformer-realtime-v2`，无需OSS即可进行语音识别！

### 当前配置

```bash
VIDEO_CUT_DASHSCOPE_API_KEY=sk-7efc7735d4864c12bdd22c397873ea9b
VIDEO_CUT_ASR_MODEL=paraformer-realtime-v2
VIDEO_CUT_OSS_FAKE_DIR=./staging
```

## 🚀 立即开始

### 方法1: 一键完成全流程

```bash
uv run video-cut run your_video.mp4 --auto
```

### 方法2: 分步执行

```bash
# 1. 提取音频
uv run video-cut extract-audio your_video.mp4

# 2. 转录（使用实时引擎，无需OSS）
uv run video-cut transcribe your_video.mp4

# 3. 分析挑片段
uv run video-cut analyze your_video.mp4

# 4. 切片合并
uv run video-cut cut your_video.mp4
```

### 方法3: Web界面

```bash
# 启动Web服务
uv run video-cut serve

# 浏览器访问 http://127.0.0.1:8462
# 在界面上操作完整流水线
```

## 📊 工作流程

```
视频文件
  ↓ extract-audio
音频文件 (m4a, 16kHz mono)
  ↓ transcribe (使用 paraformer-realtime-v2)
转录结果 (transcript.json)
  ↓ analyze
高光片段 (highlights.json)
  ↓ cut
最终视频 (merged.mp4)
```

## 🔧 核心优势

✅ **无需OSS配置** - 直接处理本地音频
✅ **实时流式识别** - WebSocket低延迟
✅ **节省成本** - 无存储和流量费用
✅ **开发友好** - 开箱即用

## ⚠️ 注意事项

1. **API Key有效性**: 确保API Key在阿里云百炼控制台有效
2. **音频格式**: extract-audio会自动转换为16kHz mono WAV格式
3. **网络连接**: 需要能访问DashScope API

## 🐛 常见问题

### Q: 提示403错误？
A: 检查API Key是否有效，登录 https://bailian.console.aliyun.com/ 验证

### Q: 如何切换回传统引擎？
A: 修改 `.env` 中的 `VIDEO_CUT_ASR_MODEL=paraformer-v2`

### Q: 需要安装额外依赖吗？
A: dashscope SDK已包含，无需额外安装

## 📝 测试脚本

运行测试验证实时引擎：

```bash
python test_realtime_asr.py
```

## 📚 详细文档

- 完整说明: `PARAFORMER_REALTIME_USAGE.md`
- 本地HTTP方案: `LOCAL_HTTP_USAGE.md`
- 实施总结: `IMPLEMENTATION_SUMMARY.md`

---

**准备好了吗？开始吧！** 🎬

```bash
uv run video-cut run your_video.mp4 --auto
```
