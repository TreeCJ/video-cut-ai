# 本地HTTP服务器替代OSS方案

## 概述

当你没有阿里云OSS配置时，可以使用本地HTTP服务器来替代OSS，让DashScope ASR服务能够访问你的音频文件。

## 使用方法

### 1. 设置环境变量

在 `.env` 文件中添加：

```bash
# 不填写OSS相关配置，改用本地目录
VIDEO_CUT_OSS_FAKE_DIR=./staging
```

或者直接通过命令行设置：

```bash
export VIDEO_CUT_OSS_FAKE_DIR=./staging
```

### 2. 运行转录命令

```bash
# 提取音频
python -m video_cut.cli extract-audio input.mp4

# 转录音频（使用本地HTTP服务器）
python -m video_cut.cli transcribe input.mp4
```

### 3. 工作流程

1. 音频文件被复制到 `~/.video-cut/staging/` 目录
2. 启动本地HTTP服务器（默认端口自动分配）
3. 生成HTTP URL提供给DashScope ASR服务
4. ASR服务从本地HTTP服务器下载音频文件
5. 转录完成后清理临时文件

## 技术细节

### 本地HTTP服务器

- **位置**: `src/video_cut/local_http.py`
- **端口**: 自动分配（首次请求时确定）
- **监听地址**: `127.0.0.1`
- **文件存储**: `~/.video-cut/staging/`

### 兼容性

- ✅ 保持原有代码逻辑不变
- ✅ 与现有测试兼容
- ✅ 无需修改ASR引擎代码
- ✅ DashScope ASR可正常访问HTTP URL

## 注意事项

1. **防火墙**: 确保本地防火墙允许127.0.0.1的HTTP连接
2. **端口冲突**: 服务器会自动选择可用端口
3. **临时文件**: 所有音频副本存储在 `~/.video-cut/staging/`
4. **单例模式**: 整个进程只启动一个HTTP服务器实例

## 故障排除

### 问题: HTTP服务器无法启动

**解决方案**: 检查是否有其他程序占用了端口，或尝试重启应用

### 问题: ASR服务无法访问HTTP URL

**解决方案**: 
1. 确认本地网络允许localhost访问
2. 检查防火墙设置
3. 查看 `~/.video-cut/staging/` 目录中是否有对应的音频文件

### 问题: 转录失败

**解决方案**: 检查日志输出，确认HTTP服务器是否正常运行

## 开发说明

如果需要手动控制HTTP服务器：

```python
from video_cut.local_http import LocalFileServer

# 获取单例实例
server = LocalFileServer.get_instance()

# 启动服务器
server.start()

# 停止服务器（通常在应用退出时自动停止）
server.stop()
```

## 与真实OSS的区别

| 特性 | 真实OSS | 本地HTTP |
|------|---------|----------|
| 需要配置 | ✅ 需要AK/SK等 | ❌ 不需要 |
| 网络访问 | 公网可访问 | 仅本地访问 |
| 成本 | 产生费用 | 免费 |
| 稳定性 | 高可用 | 依赖本地环境 |
| 适用场景 | 生产环境 | 开发/测试 |

## 推荐配置

对于开发环境，推荐在 `.env` 中配置：

```bash
# 开发环境：使用本地HTTP服务器
VIDEO_CUT_OSS_FAKE_DIR=./staging

# 生产环境：使用真实OSS（注释掉FAKE_DIR）
# VIDEO_CUT_OSS_BUCKET=your-bucket
# VIDEO_CUT_OSS_ENDPOINT=https://oss-cn-shanghai.aliyuncs.com
# VIDEO_CUT_OSS_ACCESS_KEY_ID=your-key-id
# VIDEO_CUT_OSS_ACCESS_KEY_SECRET=your-key-secret
```
