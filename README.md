# 🎬 AI 智能视频高光剪辑系统

<p align="center">
  <strong>基于人工智能的自动化视频高光提取与混剪平台</strong>
</p>

<p align="center">
  <a href="#-功能特点">功能特点</a> •
  <a href="#-技术架构">技术架构</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-部署指南">部署指南</a> •
  <a href="#-使用文档">使用文档</a>
</p>

---

## 📖 项目简介

本项目是一款面向视频内容创作者的 **AI 驱动智能高光剪辑系统**，旨在提供高效易用的自动化视频分析与精彩片段提取能力。通过整合语音识别（ASR）、大语言模型语义分析和多模态视觉场景理解，系统能够自动从长视频中识别并提取高光时刻，生成符合叙事逻辑的精彩集锦成片。

### 核心价值

- **解放创意生产力**：用 AI 替代重复性手工劳动（语音转写、片段截取、字幕嵌入）
- **降低专业剪辑门槛**：无需掌握复杂的剪辑软件操作，一键生成高质量视频
- **提升批量处理效率**：支持大批量场景的自动化处理与多版本管理
- **智能化内容理解**：超越简单的时间轴切割，实现基于叙事结构的智能剪辑

### 目标用户

- 🎥 **自媒体创作者**：快速从直播回放、录播素材中提取精彩片段
- 🎓 **教育机构**：自动生成课程高光集锦、知识点切片
- 🎬 **影视制作团队**：辅助粗剪阶段的高光预筛选与版本对比
- 💼 **企业内容部门**：批量处理会议记录、培训视频、宣传素材

---

## ✨ 功能特点

### 核心功能

- **🎯 智能高光提取**
  - 基于台词文本分析的 LLM 智能筛选
  - Qwen-VL 多模态视觉识别的场景匹配
  - 围绕指定主题自动提取高光片段并混剪成片

- **🔊 完整的字幕处理能力**
  - 语音识别（Paraformer-realtime-v2）
  - 字幕纠错与繁简转换
  - 智能断句与时间轴对齐
  - 一键开关字幕和多语言选择（中文/英语/日语等）

- **🎞️ 专业的视频处理**
  - 大文件切片上传（最大 5GB）
  - BGM 自动混音
  - 成片时长智能控制（2-3 分钟）
  - 多版本管理与对比

- **📊 完善的任务管理**
  - 任务状态实时推送（SSE）
  - 完整的生命周期管理（创建/查看/删除）
  - 层级化数据结构（视频任务 → 生成版本 → 剪辑片段）

---

## 🏗️ 技术架构

### 技术栈

| 分类 | 技术 |
|------|------|
| **前端** | HTML5, JavaScript, Jinja2 模板引擎, 原生 CSS |
| **后端** | Python, FastAPI, SQLAlchemy ORM |
| **数据库** | MySQL, SQLite（双数据库支持） |
| **AI 集成** | DashScope API（Paraformer ASR, Qwen-Max LLM, Qwen-VL 视觉分析） |
| **视频处理** | MoviePy, FFmpeg |
| **认证安全** | JWT, bcrypt, HTTP-only Cookie |
| **实时通信** | SSE (Server-Sent Events) |
| **部署** | Uvicorn ASGI 服务器, Docker Compose |

### 架构图

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend  │────▶│  FastAPI     │────▶│   MySQL/    │
│  (Browser)  │◀────│  (Backend)   │◀────│   SQLite    │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
            ┌─────────────┐ ┌──────────────┐
            │ DashScope   │ │  FFmpeg +    │
            │ (ASR/LLM/VL)│ │  MoviePy     │
            └─────────────┘ └──────────────┘
```

### 核心技术特点

1. **前后端分离架构**：FastAPI 构建 RESTful API，SQLAlchemy 管理数据持久化
2. **AI 深度集成**：
   - Paraformer-realtime-v2 实现高精度语音识别与时间戳对齐
   - Qwen-Max 大语言模型进行台词语义分析、高光片段智能筛选
   - Qwen-VL 视觉模型进行画面场景分析
3. **智能视频处理流水线**：MoviePy + FFmpeg 协同工作，支持视频切片、字幕嵌入、多版本合成
4. **实时交互体验**：SSE 实现任务进度实时推送，自定义模态对话框与 Toast 通知
5. **Windows 路径兼容**：智能处理 Windows 反斜杠路径与 URL 正斜杠转换

---

## 🚀 快速开始

### 环境要求

- Python ≥ 3.10
- FFmpeg（用于视频处理）
- MySQL（可选，默认使用 SQLite）
- DashScope API Key（阿里云百炼）

### 安装步骤

#### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/video-cut-ai.git
cd video-cut-ai
```

#### 2. 安装依赖

```bash
pip install -r requirements.txt
# 或使用 uv（推荐）
uv sync --extra dev
```

#### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# DashScope API 配置
VIDEO_CUT_DASHSCOPE_API_KEY=your_api_key_here
VIDEO_CUT_ASR_MODEL=paraformer-realtime-v2
VIDEO_CUT_LLM_MODEL=qwen-max

# 数据库配置（可选，默认使用 SQLite）
# VIDEO_CUT_DATABASE_URL=mysql+pymysql://user:password@localhost:3306/video_cut

# JWT 密钥（生产环境务必修改）
JWT_SECRET_KEY=your-secret-key-change-in-production
```

#### 4. 启动服务

```bash
# 开发模式（带热重载）
python -m uvicorn src.video_cut.web.app:create_app_dev --reload --host 0.0.0.0 --port 8462

# 或使用启动脚本
python start_server.py
```

访问 http://localhost:8462 开始使用！

---

## 📦 Docker 部署

### 一键部署

```bash
docker-compose up -d
```

### 配置文件

`docker-compose.yml` 已包含完整配置：

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8462:8462"
    environment:
      - VIDEO_CUT_DASHSCOPE_API_KEY=your_key
      - VIDEO_CUT_DATABASE_URL=sqlite:///./video_cut.db
    volumes:
      - ./output:/app/output
```

---

## 📚 使用文档

### 基本工作流程

```bash
# 1. 跑分析，提取高光片段
video-cut run input.mp4 -p "突出人物冲突"

# 2. 在 Web 界面编辑 highlights.json（可选）

# 3. 切片合并生成最终视频
video-cut cut input.mp4
```

### Web 界面功能

1. **视频上传与管理**
   - 支持拖拽上传（最大 5GB）
   - 视频任务列表与搜索
   - 多版本管理与对比

2. **智能剪辑**
   - 自动语音识别与转录
   - AI 智能高光提取
   - 可视化时间轴编辑

3. **字幕处理**
   - 自动生成字幕文件
   - 繁简转换与纠错
   - 一键嵌入视频

4. **导出与下载**
   - 多格式导出（MP4, MOV 等）
   - 带字幕/无字幕版本
   - 批量下载

---

## 🔧 常见问题

### 1. ffmpeg 找不到

**macOS**:
```bash
brew install ffmpeg
```

**Windows**:
```powershell
winget install --id Gyan.FFmpeg
# 然后手动将 ffmpeg.exe 所在目录加入 PATH
```

### 2. 端口被占用

```bash
# macOS
lsof -ti:8462 | xargs kill

# Windows
netstat -ano | findstr 8462
taskkill /PID <pid> /F
```

### 3. OSS 403 错误

检查 AccessKey 权限，确保 RAM 子账号拥有 `oss:PutObject`、`oss:GetObject`、`oss:DeleteObject` 权限。

### 4. ASR 无法下载音频

OSS endpoint 必须是 HTTPS 公网地址，内网 endpoint DashScope 无法访问。

---

## 📝 开发指南

### 项目结构

```
src/video_cut/
├── cli.py              # CLI 入口
├── config.py           # 配置管理
├── audio.py            # 音频处理
├── transcribe.py       # 语音识别
├── cutting.py          # 视频剪辑
├── auth/               # 认证模块
├── db/                 # 数据库模型
├── services/           # 业务逻辑
└── web/                # Web 界面
    ├── app.py          # FastAPI 应用
    ├── auth.py         # 认证路由
    ├── clip_management.py  # 剪辑管理
    └── templates/      # HTML 模板
```

### 运行测试

```bash
pytest tests/
```

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- [DashScope](https://dashscope.aliyun.com/) - 提供强大的 AI 能力
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能的 Web 框架
- [FFmpeg](https://ffmpeg.org/) - 音视频处理利器
- [MoviePy](https://zulko.github.io/moviepy/) - Python 视频编辑库

---

## 📮 联系方式

如有问题或建议，请通过以下方式联系：

- 📧 Email: your_email@example.com
- 💬 提交 Issue: https://github.com/YOUR_USERNAME/video-cut-ai/issues

---

<p align="center">Made with ❤️ by Your Team</p>
