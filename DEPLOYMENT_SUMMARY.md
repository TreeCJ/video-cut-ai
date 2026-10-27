# 🐳 Docker 部署完成！

你的 video-cut 应用现在已经完全支持 Docker 部署了。

## ✅ 已创建的文件

### Docker 核心文件
- `Dockerfile` - 多阶段构建的生产级镜像
- `docker-compose.yml` - 完整的服务编排配置
- `.dockerignore` - 构建时排除的文件列表
- `.env.production` - 生产环境配置模板

### 配置文件
- `deploy/mysql/init.sql` - MySQL 初始化脚本
- `deploy/nginx/nginx.conf` - Nginx 反向代理配置
- `deploy.sh` - Linux/Mac 快速部署脚本
- `deploy.bat` - Windows 快速部署脚本

### 文档
- `DOCKER.md` - 完整的 Docker 部署指南

## 🚀 快速开始（3步部署）

### 方式 1：使用部署脚本（推荐）

**Windows:**
```bash
deploy.bat
```

**Linux/Mac:**
```bash
./deploy.sh
```

### 方式 2：手动部署

```bash
# 1. 复制并配置环境变量
cp .env.production .env
# 编辑 .env 文件，修改密码和 API Key

# 2. 启动服务
docker-compose up -d

# 3. 查看状态
docker-compose ps
```

## 📋 部署前检查清单

- [ ] 安装 Docker Desktop (Windows/Mac) 或 Docker Engine (Linux)
- [ ] 安装 Docker Compose v2.0+
- [ ] 准备至少 4GB RAM 和 20GB 磁盘空间
- [ ] 获取 DashScope API Key

## ⚙️ 必须修改的配置

在 `.env` 文件中修改以下值：

1. **JWT_SECRET_KEY**: 生成强密钥
   ```bash
   openssl rand -hex 32
   ```

2. **MYSQL_ROOT_PASSWORD**: MySQL root 密码
3. **MYSQL_PASSWORD**: 数据库用户密码
4. **VIDEO_CUT_DASHSCOPE_API_KEY**: 你的 DashScope API Key

## 🎯 访问应用

部署成功后，可以通过以下地址访问：

- **应用界面**: http://localhost:8462
- **MySQL**: localhost:3310（外部工具连接）
- **Redis**: localhost:6379（如果需要）

**默认登录凭据:**
- 用户名: `admin`
- 密码: `admin123`
- ⚠️ 首次登录后立即修改密码！

## 📊 服务架构

```
Internet
    │
    ▼
┌─────────┐
│ Nginx   │ ← 反向代理 + SSL (可选)
└────┬────┘
     │
     ▼
┌─────────┐
│  App    │ ← FastAPI 应用 (端口 8462)
└────┬────┘
     │
     ├──────────┐
     │          │
     ▼          ▼
┌────────┐  ┌────────┐
│ MySQL  │  │ Redis  │
└────────┘  └────────┘
```

## 🔧 常用命令

```bash
# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f app

# 重启服务
docker-compose restart app

# 停止所有服务
docker-compose down

# 停止并删除数据（危险！）
docker-compose down -v

# 进入容器
docker-compose exec app bash
```

## 💾 数据备份

```bash
# 备份数据库
docker-compose exec mysql mysqldump -u root -p video_cut > backup.sql

# 备份视频文件
docker run --rm -v video-cut_app_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/videos.tar.gz /data
```

## 🔐 安全建议

1. **修改默认密码**
   - 立即修改 admin 账户密码
   - 使用强密码策略

2. **生成强 JWT 密钥**
   ```bash
   openssl rand -hex 32
   ```

3. **启用 HTTPS**（生产环境）
   ```bash
   # 放置 SSL 证书到 deploy/nginx/ssl/
   docker-compose --profile production up -d
   ```

4. **防火墙配置**
   - 只开放必要的端口
   - 限制数据库外部访问

5. **定期更新**
   ```bash
   docker-compose pull
   docker-compose up -d --build
   ```

## 🐛 故障排除

### 端口被占用
```bash
# 查看哪个进程占用了端口
netstat -ano | findstr :8462  # Windows
lsof -i :8462                  # Linux/Mac

# 修改 .env 中的端口号
APP_PORT=8463
```

### 容器启动失败
```bash
# 查看详细日志
docker-compose logs

# 重新构建镜像
docker-compose build --no-cache
```

### 数据库连接失败
```bash
# 检查 MySQL 是否就绪
docker-compose ps mysql

# 重置数据库（会丢失数据！）
docker-compose down -v
docker-compose up -d
```

## 📚 更多信息

- 详细文档：查看 `DOCKER.md`
- 认证系统：查看 `AUTHENTICATION.md`
- 快速指南：查看 `AUTH_SETUP.md`

## 🎉 下一步

1. ✅ 部署应用到 Docker
2. ⬜ 配置 SSL/TLS 证书
3. ⬜ 设置自动备份
4. ⬜ 配置监控系统
5. ⬜ 设置日志聚合

---

**祝你部署顺利！🚀**

如有问题，请查看日志：`docker-compose logs -f`
