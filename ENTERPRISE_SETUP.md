# 企业级视频剪辑平台使用指南

## 📋 目录

- [快速开始](#快速开始)
- [数据库配置](#数据库配置)
- [版本管理](#版本管理)
- [API使用](#api使用)
- [部署指南](#部署指南)

---

## 快速开始

### 1. 初始化数据库

```bash
# 进入项目目录
cd video-cut-main

# 激活虚拟环境
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 运行数据库初始化脚本
python scripts/init_db.py
```

### 2. 启动Web服务

```bash
video-cut serve --port 8462
```

访问 http://127.0.0.1:8462 查看Web界面

---

## 数据库配置

### 开发环境（SQLite）

默认使用SQLite，无需额外配置：

```env
VIDEO_CUT_DATABASE_URL=sqlite:///./video_cut.db
```

### 生产环境（MySQL）

```env
VIDEO_CUT_DATABASE_URL=mysql+pymysql://user:password@localhost:3306/video_cut
```

### 生产环境（PostgreSQL）

```env
VIDEO_CUT_DATABASE_URL=postgresql://user:password@localhost:5432/video_cut
```

---

## 版本管理

### 核心概念

**版本 (Version)**: 每次生成高光片段和合并视频都会创建一个新版本，保留完整历史。

**软删除 (Soft Delete)**: 删除版本时只是标记为删除，可以随时恢复。

**激活版本 (Active Version)**: 当前正在使用的版本，可以随时切换到历史版本。

### 版本操作流程

#### 1. 创建新版本

通过Web界面点击"重新生成"按钮，或在详情页操作。

每次生成会：
- 保存当前配置（提示词、时长等）
- 生成新的高光JSON
- 创建新的剪辑片段
- 生成新的合并视频

#### 2. 查看版本历史

在视频详情页可以看到所有版本：

```
版本 v3 [当前版本] [带字幕] ✅ 已完成
  创建时间: 2026-10-23 15:30
  文件大小: 45.2 MB
  片段数: 8

版本 v2 [带字幕] ✅ 已完成
  创建时间: 2026-10-23 14:20
  文件大小: 42.8 MB
  片段数: 7

版本 v1 ❌ 已删除
  删除时间: 2026-10-23 14:15
  [恢复按钮]
```

#### 3. 切换版本

点击任意版本的"切换到此版本"按钮，即可将该版本设为当前激活版本。

#### 4. 删除版本

点击"删除"按钮，版本会被标记为删除但不会真正从磁盘移除。

可以随时点击"恢复"按钮恢复已删除的版本。

---

## API使用

### 列出版本

```bash
curl http://localhost:8462/api/videos/1/versions
```

响应：
```json
{
  "video_id": 1,
  "current_version_id": 3,
  "total_versions": 3,
  "versions": [
    {
      "id": 3,
      "version_number": 3,
      "status": "completed",
      "created_at": "2026-10-23T15:30:00",
      "is_active": true,
      "with_subtitles": true,
      "file_size": 47400000,
      "clip_count": 8
    }
  ]
}
```

### 创建新版本

```bash
curl -X POST http://localhost:8462/api/videos/1/versions \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "重点选取冲突和高潮部分",
    "max_duration": 180,
    "with_subtitles": true
  }'
```

### 删除版本

```bash
curl -X DELETE http://localhost:8462/api/videos/1/versions/2 \
  -H "Content-Type: application/json" \
  -d '{"reason": "不再需要这个版本"}'
```

### 恢复版本

```bash
curl -X POST http://localhost:8462/api/videos/1/versions/2/restore
```

### 切换版本

```bash
curl -X POST http://localhost:8462/api/videos/1/versions/1/switch
```

---

## 文件系统结构

```
/media_storage/processed/{video_id}/
├── versions/
│   ├── v1/                    # 版本1
│   │   ├── highlights.json
│   │   ├── merged.mp4
│   │   └── clips/
│   │       ├── 01-xxx.mp4
│   │       └── subtitled/
│   │           └── 01-xxx.mp4
│   ├── v2/                    # 版本2
│   │   └── ...
│   └── v3/                    # 版本3
│       └── ...
├── audio.m4a                  # 共享音频
└── transcript.json            # 共享转录
```

---

## 清理策略

定期清理已删除的旧版本以释放磁盘空间：

```bash
# 手动清理30天前的已删除版本
python scripts/cleanup_old_versions.py --days 30

# 设置定时任务（每周日凌晨2点执行）
crontab -e
# 添加：
0 2 * * 0 /path/to/video-cut-main/scripts/cleanup_old_versions.py >> /var/log/vc_cleanup.log 2>&1
```

---

## 部署指南

### Docker Compose部署

创建 `docker-compose.yml`:

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
      MYSQL_DATABASE: video_cut
      MYSQL_USER: ${DB_USER}
      MYSQL_PASSWORD: ${DB_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

  api:
    build: .
    environment:
      DATABASE_URL: mysql://${DB_USER}:${DB_PASSWORD}@mysql:3306/video_cut
      REDIS_URL: redis://redis:6379
      MEDIA_STORAGE_PATH: /media_storage
    volumes:
      - ./backend:/app
      - /media_storage:/media_storage
    ports:
      - "8000:8000"
    depends_on:
      - mysql
      - redis
    restart: unless-stopped

  worker:
    build: .
    command: celery -A tasks.celery_app worker --loglevel=info --concurrency=4
    environment:
      DATABASE_URL: mysql://${DB_USER}:${DB_PASSWORD}@mysql:3306/video_cut
      REDIS_URL: redis://redis:6379
      MEDIA_STORAGE_PATH: /media_storage
    volumes:
      - ./backend:/app
      - /media_storage:/media_storage
    depends_on:
      - mysql
      - redis
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    volumes:
      - ./frontend/dist:/usr/share/nginx/html
      - ./nginx.conf:/etc/nginx/nginx.conf
      - /media_storage:/media_storage:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  mysql_data:
```

### 环境变量配置

创建 `.env` 文件：

```env
# 数据库
DATABASE_URL=mysql://videocut:password@localhost:3306/videocut

# Redis
REDIS_URL=redis://localhost:6379/0

# 媒体存储路径
MEDIA_STORAGE_PATH=/media_storage

# DashScope API
VIDEO_CUT_DASHSCOPE_API_KEY=your-api-key-here

# LLM模型
VIDEO_CUT_LLM_MODEL=qwen-max
```

---

## 常见问题

### Q: 如何备份数据库？

```bash
# MySQL备份
mysqldump -u user -p video_cut > backup_$(date +%Y%m%d).sql

# 恢复
mysql -u user -p video_cut < backup_20261023.sql
```

### Q: 版本太多占用空间怎么办？

设置自动清理策略，定期清理30天前的已删除版本。

### Q: 可以导出某个版本的所有配置吗？

```bash
curl http://localhost:8462/api/videos/1/versions/3 | jq > version_config.json
```

---

## 技术支持

如有问题，请提交Issue或联系技术支持团队。
