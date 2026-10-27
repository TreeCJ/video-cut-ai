# 用户认证系统 - 快速开始指南

## ✅ 已完成的功能

### 1. 核心功能
- **JWT Token 认证**：安全的基于 token 的认证系统
- **密码加密**：使用 bcrypt 进行安全的密码哈希存储
- **角色权限控制**：三种角色（Admin、Editor、Viewer）
- **用户管理界面**：管理员可以创建、编辑、删除用户
- **会话管理**：24小时 token 过期时间

### 2. API 端点
- `POST /auth/login` - 用户登录
- `POST /auth/register` - 注册新用户
- `POST /auth/logout` - 用户登出
- `GET /auth/me` - 获取当前用户信息
- `GET /admin/users` - 用户列表（仅管理员）
- `PUT /admin/users/{id}` - 更新用户（仅管理员）
- `DELETE /admin/users/{id}` - 删除用户（仅管理员）

### 3. 前端页面
- `/login` - 登录页面
- `/register` - 注册页面（仅管理员可访问）
- `/admin/users` - 用户管理页面（仅管理员）

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install passlib[bcrypt] PyJWT
```

### 2. 初始化数据库

```bash
# 加载环境变量并初始化
export $(cat .env | grep -v '^#' | xargs)
python src/video_cut/db/init_db.py
```

这将：
- 创建所有必要的数据库表
- 创建默认管理员账户：
  - 用户名：`admin`
  - 密码：`admin123`
  - ⚠️ **重要**：首次登录后请立即修改密码！

### 3. 启动服务器

```bash
python start_server.py
```

服务器将在 `http://127.0.0.1:8464` 启动

### 4. 登录系统

1. 打开浏览器访问：`http://127.0.0.1:8464/login`
2. 使用默认凭据登录：
   - Username: `admin`
   - Password: `admin123`
3. 登录后可以访问用户管理页面创建其他用户

## 🔐 安全建议

### 生产环境部署前必须做的事：

1. **修改默认管理员密码**
   - 立即修改 admin 账户的密码

2. **设置强 JWT 密钥**
   ```bash
   # 在 .env 文件中设置
   JWT_SECRET_KEY=$(openssl rand -hex 32)
   ```

3. **使用 HTTPS**
   - 确保生产环境使用 SSL/TLS 证书

4. **配置正确的数据库**
   - 使用 MySQL 或 PostgreSQL，不要用 SQLite

5. **备份数据库**
   - 定期备份用户数据

## 👥 用户角色说明

### Admin（管理员）
- ✅ 所有权限
- ✅ 管理用户（创建、编辑、删除）
- ✅ 管理所有视频和项目
- ✅ 访问管理员面板

### Editor（编辑者）
- ✅ 上传和处理视频
- ✅ 创建和编辑剪辑
- ❌ 不能管理用户
- ✅ 默认角色

### Viewer（查看者）
- ✅ 只读访问视频和剪辑
- ❌ 不能修改或删除内容
- ❌ 不能管理用户

## 🧪 测试认证系统

运行测试脚本验证认证系统：

```bash
python test_auth.py
```

预期输出：
```
============================================================
Authentication System Test
============================================================
Testing login...
✓ Login successful!
  User ID: 1
  Username: admin
  Role: admin

Testing /auth/me...
✓ Got user info:
  Username: admin
  Email: admin@localhost
  Role: admin

Testing unauthorized access...
✓ Correctly rejected unauthorized request (401)

============================================================
All tests passed! ✓
============================================================
```

## 📝 开发指南

### 保护新的 API 路由

```python
from fastapi import Depends
from video_cut.auth import get_current_user
from video_cut.db.models import User

@app.get("/protected")
def protected_route(current_user: User = Depends(get_current_user)):
    # 只有认证用户可以访问
    return {"message": f"Hello {current_user.username}"}
```

### 要求特定角色

```python
from video_cut.auth import require_role

@app.get("/admin-only")
def admin_route(current_user: User = Depends(require_role("admin"))):
    # 只有管理员可以访问
    return {"message": "Admin access granted"}
```

## 🛠️ 故障排除

### "Invalid username or password" 错误

1. 确认数据库已正确初始化
2. 检查数据库连接字符串
3. 重置管理员密码：
   ```bash
   python reset_admin_password.py
   ```

### 数据库连接失败

1. 检查 `.env` 文件中的 `VIDEO_CUT_DATABASE_URL`
2. 确认 MySQL/PostgreSQL 服务正在运行
3. 验证数据库权限

### Token 过期

- Token 默认 24 小时后过期
- 过期后重新登录即可
- 可以在 `.env` 中修改 `ACCESS_TOKEN_EXPIRE_MINUTES`

## 📚 更多信息

详细文档请参考：
- [AUTHENTICATION.md](AUTHENTICATION.md) - 完整的技术文档
- [API Documentation](http://127.0.0.1:8464/docs) - Swagger UI 自动生成的 API 文档

## ✨ 功能特点

- 🔒 安全的密码哈希（bcrypt）
- 🎫 JWT token 认证（HTTP-only cookies）
- 👥 基于角色的访问控制
- 🎨 美观的暗色主题 UI
- 📱 响应式设计
- 🚀 简单易用的 API
- 📊 完整的用户审计日志

---

**享受你的视频剪辑工作吧！** 🎬
