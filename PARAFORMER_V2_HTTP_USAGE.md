# Paraformer-v2 本地HTTP服务器方案使用指南

## 概述

已实现 paraformer-v2 模型的本地HTTP服务器方案，无需OSS即可使用。该方案通过本地HTTP服务器提供音频文件的HTTPS URL。

## 工作原理

```
本地音频文件 (m4a/mp3)
    ↓
转换为WAV格式
    ↓
本地HTTP服务器 (0.0.0.0:8080)
    ↓
Ngrok隧道 (可选，提供公网HTTPS URL)
    ↓
DashScope API (paraformer-v2)
    ↓
转录结果 (transcript.json)
```

## 配置

### `.env` 文件

```bash
# DashScope API Key
VIDEO_CUT_DASHSCOPE_API_KEY=sk-7efc7735d4864c12bdd22c397873ea9b

# 使用 paraformer-v2 模型
VIDEO_CUT_ASR_MODEL=paraformer-v2

# Ngrok认证令牌（可选，但强烈推荐）
# 从 https://dashboard.ngrok.com/get-started/your-authtoken 获取
VIDEO_CUT_NGROK_AUTH_TOKEN=your_ngrok_auth_token_here
```

## 安装依赖

### 基础依赖（必需）

```bash
pip install dashscope httpx
```

### Ngrok支持（推荐）

```bash
pip install pyngrok
```

**注意**: ngrok需要注册账号获取authtoken（免费）

## 使用方法

### 方法1: 使用Ngrok（推荐）

**优点**: 
- 真正的公网HTTPS URL
- DashScope可以可靠访问
- 稳定性高

**步骤**:

1. 注册Ngrok账号: https://dashboard.ngrok.com/signup
2. 获取Authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
3. 在 `.env` 中配置:
   ```bash
   VIDEO_CUT_NGROK_AUTH_TOKEN=your_actual_ngrok_token
   VIDEO_CUT_ASR_MODEL=paraformer-v2
   ```
4. 运行:
   ```bash
   uv run video-cut run your_video.mp4 --auto
   ```

### 方法2: 不使用Ngrok

**缺点**:
- 仅本地HTTP URL
- DashScope可能无法访问
- 适合测试环境

**步骤**:

1. 不配置 `VIDEO_CUT_NGROK_AUTH_TOKEN`
2. 直接运行:
   ```bash
   uv run video-cut run your_video.mp4 --auto
   ```

## 两种模型对比

| 特性 | paraformer-realtime-v2 | paraformer-v2 |
|------|------------------------|---------------|
| **识别方式** | WebSocket实时流式 | HTTP异步任务 |
| **音频处理** | 本地文件直接读取 | 需要HTTPS URL |
| **OSS需求** | ❌ 不需要 | ❌ 不需要(用HTTP服务器) |
| **Ngrok需求** | ❌ 不需要 | ✅ 推荐(提高可靠性) |
| **延迟** | 低(实时) | 中等(轮询) |
| **适用场景** | 实时应用、开发 | 批量处理、生产 |
| **成本** | 仅API费用 | API + Ngrok(免费) |

## 完整示例

### 切换到 paraformer-v2

```bash
# 1. 修改 .env
VIDEO_CUT_ASR_MODEL=paraformer-v2
VIDEO_CUT_NGROK_AUTH_TOKEN=your_token_here

# 2. 运行
uv run video-cut run "C:\Users\admin\Downloads\《甄嬛传》 第73集.mp4" --auto
```

### 切换回 paraformer-realtime-v2

```bash
# 1. 修改 .env
VIDEO_CUT_ASR_MODEL=paraformer-realtime-v2

# 2. 运行
uv run video-cut run "C:\Users\admin\Downloads\《甄嬛传》 第73集.mp4" --auto
```

## 技术细节

### 本地HTTP服务器

- **端口**: 8080 (自动递增如果占用)
- **监听地址**: 0.0.0.0 (允许外部访问)
- **文件存储**: `~/.video-cut/http-staging/`
- **生命周期**: 进程级别单例
- **自动清理**: 转录完成后删除临时文件

### Ngrok隧道

- **作用**: 将本地HTTP服务暴露为公网HTTPS URL
- **免费额度**: 足够个人使用
- **URL变化**: 每次重启会生成新URL
- **安全性**: HTTPS加密，有auth token保护

### 音频处理流程

```python
# 1. 提取音频 (M4A格式)
extract_audio(video_path, audio_path)

# 2. 上传到HTTP服务器
http_server = LocalHttpAudioServer.get_instance()
audio_url = http_server.upload(audio_path)  
# 返回: https://xxx.ngrok.io/uuid-audio.m4a

# 3. 提交转录任务
engine = ParaformerStandardEngine(api_key)
transcript = engine.transcribe(audio_url)

# 4. 清理临时文件
http_server.delete(audio_url)
```

## 故障排除

### 问题1: Ngrok连接失败

**症状**: "Failed to setup ngrok"

**解决**:
1. 检查authtoken是否正确
2. 确认ngrok账号活跃
3. 查看ngrok dashboard的连接数

### 问题2: 端口被占用

**症状**: "Address already in use"

**解决**: 自动尝试下一个端口（8081, 8082...）

### 问题3: DashScope无法访问音频

**症状**: "Model.AccessDenied" 或超时

**解决**:
1. 确保配置了ngrok
2. 检查ngrok隧道是否活跃
3. 验证URL是HTTPS格式

### 问题4: 转录结果为空

**症状**: "No transcription results"

**解决**:
1. 检查音频文件是否有效
2. 确认音频时长不要太短
3. 查看日志中的详细错误

## 性能优化

### 并行处理

对于多个视频，可以并行运行：

```bash
# 终端1
VIDEO_CUT_ASR_MODEL=paraformer-v2 uv run video-cut run video1.mp4 --auto

# 终端2  
VIDEO_CUT_ASR_MODEL=paraformer-v2 uv run video-cut run video2.mp4 --auto
```

### 缓存策略

转录结果会保存在 `output/<视频名>/transcript.json`，重复运行时会跳过。

使用 `--force` 强制重新转录：

```bash
uv run video-cut transcribe your_video.mp4 --force
```

## 代码结构

### 核心文件

- `src/video_cut/asr/paraformer_standard.py` - paraformer-v2引擎
- `src/video_cut/http_storage.py` - 本地HTTP服务器
- `src/video_cut/transcribe.py` - 转录编排逻辑
- `src/video_cut/cli.py` - CLI集成

### 关键类

```python
# HTTP服务器
LocalHttpAudioServer
  - get_instance()      # 单例模式
  - start()             # 启动服务器
  - upload(path)        # 上传并返回URL
  - delete(url)         # 清理文件

# ASR引擎
ParaformerStandardEngine
  - transcribe(url)     # 转录音频
  - _submit(url)        # 提交任务
  - _poll(task_id)      # 轮询结果
```

## 最佳实践

1. **开发环境**: 使用 paraformer-realtime-v2（简单、快速）
2. **生产环境**: 使用 paraformer-v2 + Ngrok（稳定、可靠）
3. **批量处理**: 使用 paraformer-v2（适合异步任务）
4. **实时应用**: 使用 paraformer-realtime-v2（低延迟）

## 总结

✅ **已完成**:
- paraformer-v2 本地HTTP服务器方案
- Ngrok公网HTTPS URL支持
- 自动音频格式转换
- 临时文件自动清理

✅ **优势**:
- 无需OSS配置
- 支持公网访问
- 稳定可靠
- 易于部署

✅ **下一步**:
- 注册Ngrok获取authtoken
- 配置 `.env` 文件
- 运行测试验证

现在你有两个完整的方案可供选择！🎉
