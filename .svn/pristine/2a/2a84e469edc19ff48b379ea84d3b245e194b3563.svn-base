# 测试结果与使用建议

## 📊 Paraformer-v2 测试结果

### ❌ 测试结论：**不推荐使用**

**问题**: DashScope无法访问本地HTTP URL

**错误信息**:
```
ASR task f50b4f62-b3e3-4f0e-b311-ab8cdc04cbc2 ended with status FAILED
```

**根本原因**: 
- 本地URL `http://127.0.0.1:8080/xxx.wav` 只能本机访问
- DashScope的服务器在云端，无法访问你的本地地址
- 需要公网HTTPS URL

### 🔧 解决方案对比

| 方案 | 状态 | 可靠性 | 复杂度 | 推荐度 |
|------|------|--------|--------|--------|
| **paraformer-realtime-v2** | ✅ 已测试通过 | 高 | 低 | ⭐⭐⭐⭐⭐ |
| paraformer-v2 + Ngrok | ⚠️ 未测试 | 中 | 高 | ⭐⭐ |
| paraformer-v2 + 自建HTTPS | ❌ 不可行 | - | 很高 | ⭐ |

## ✅ 推荐方案：Paraformer-Realtime-v2

### 测试结果

**成功运行**: ✓
- 音频提取: ✓
- 语音转录: ✓ (514个句子)
- 高光分析: ✓ (12个片段)
- 视频切片: ✓ (12个MP4)
- 视频合并: ✓ (merged.mp4)

**处理时间**: ~7分钟 (28分钟视频)

### 优势

1. **无需OSS配置** - 完全本地运行
2. **无需Ngrok** - 直接读取本地文件
3. **实时流式** - 低延迟识别
4. **稳定可靠** - 已验证可用
5. **简单易用** - 开箱即用

### 使用方法

```bash
# 当前配置（已设置）
VIDEO_CUT_ASR_MODEL=paraformer-realtime-v2

# 直接运行
uv run video-cut run "C:\Users\admin\Downloads\《甄嬛传》 第73集.mp4" --auto
```

## ⚠️ Paraformer-v2 的问题

### 为什么需要公网URL？

```
你的电脑                    DashScope云服务
┌──────────────┐           ┌──────────────┐
│ 本地HTTP服务器 │ ──────→  │ ASR API      │
│ 127.0.0.1:8080│   ✗失败  │ (阿里云云端)  │
└──────────────┘  无法访问  └──────────────┘
```

DashScope的paraformer-v2是**异步任务API**：
1. 你提交一个HTTPS URL
2. DashScope的服务器去下载音频
3. 处理完成后返回结果

**问题**: DashScope的服务器无法访问你的本地地址！

### 唯一解决方案：Ngrok

```
你的电脑                    Ngrok隧道                DashScope云服务
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ 本地HTTP服务器 │ ──→  │ Ngrok网关    │ ──→  │ ASR API      │
│ 127.0.0.1:8080│      │ https://...  │      │ (可以访问!)   │
└──────────────┘      └──────────────┘      └──────────────┘
```

**缺点**:
- 需要注册Ngrok账号
- 需要配置auth token
- 每次重启URL会变化
- 免费版本有带宽限制
- 增加了一层故障点

## 🎯 最终建议

### 强烈推荐：继续使用 Paraformer-Realtime-v2

**理由**:
1. ✅ **已经验证可用** - 完整流程测试通过
2. ✅ **配置简单** - 无需额外服务
3. ✅ **性能更好** - 实时流式，延迟低
4. ✅ **成本更低** - 无Ngrok费用
5. ✅ **更稳定** - 少一层依赖

**当前配置已优化**:
```bash
VIDEO_CUT_ASR_MODEL=paraformer-realtime-v2  ← 已设置
```

### 何时考虑 Paraformer-v2？

仅在以下情况：
- 你需要批量处理大量音频（>100个/天）
- 你需要离线任务队列（提交后等待完成）
- 你已经配置好Ngrok或其他内网穿透方案

## 📝 代码状态

### 已实现的功能

✅ **Paraformer-Realtime-v2引擎** (`src/video_cut/asr/paraformer_realtime.py`)
- WAV格式自动转换
- 100ms分片流式传输
- WebSocket实时返回
- 完整的错误处理

⚠️ **Paraformer-v2引擎** (`src/video_cut/asr/paraformer_standard.py`)
- HTTP异步任务API
- 轮询机制
- **但需要公网URL才能工作**

⚠️ **本地HTTP服务器** (`src/video_cut/http_storage.py`)
- 单例模式
- 自动端口管理
- **但本地URL DashScope无法访问**

### 不需要的组件

❌ **OSS相关代码** - 已完全移除
❌ **_FakeStorage类** - 已删除
❌ **复杂的URL生成逻辑** - 简化为直接文件路径

## 🚀 下一步行动

### 立即可以做的

```bash
# 当前配置已经是最佳方案
cat .env | grep ASR_MODEL
# 输出: VIDEO_CUT_ASR_MODEL=paraformer-realtime-v2

# 继续处理更多视频
uv run video-cut run another_video.mp4 --auto
```

### 如果未来需要 Paraformer-v2

1. 注册Ngrok: https://dashboard.ngrok.com/signup
2. 获取Auth Token
3. 配置到 `.env`:
   ```bash
   VIDEO_CUT_NGROK_AUTH_TOKEN=your_token_here
   VIDEO_CUT_ASR_MODEL=paraformer-v2
   ```
4. 安装pyngrok: `pip install pyngrok`
5. 重新运行

## 📈 性能对比总结

| 指标 | Realtime-v2 | V2+Ngrok |
|------|-------------|----------|
| **首次运行时间** | ~7分钟 | ~7分钟 + Ngrok启动 |
| **稳定性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **配置复杂度** | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **维护成本** | 低 | 中(需管理Ngrok) |
| **适用场景** | 日常使用、开发 | 批量处理、生产 |

## 🎉 结论

**保持当前配置，使用 paraformer-realtime-v2！**

它已经被完整测试并证明：
- ✅ 功能完整
- ✅ 性能优秀  
- ✅ 稳定可靠
- ✅ 易于使用

无需额外的配置或工具，开箱即用。

---

**最后更新**: 2026-10-22
**测试视频**: 《甄嬛传》第73集 (28分钟)
**成功输出**: 12个高光片段 + 合并视频
