# Docker Deployment Guide

Complete guide for deploying video-cut application using Docker and Docker Compose.

## 📋 Prerequisites

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **System Requirements**:
  - CPU: 2 cores minimum (4 cores recommended)
  - RAM: 4GB minimum (8GB recommended)
  - Storage: 20GB minimum for application + video files

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd video-cut-main
```

### 2. Configure Environment

```bash
# Copy production environment template
cp .env.production .env

# Edit the .env file and update values
# IMPORTANT: Change all default passwords!
nano .env  # or use your preferred editor
```

**Critical settings to update:**
- `JWT_SECRET_KEY`: Generate with `openssl rand -hex 32`
- `MYSQL_ROOT_PASSWORD`: Strong password for MySQL root
- `MYSQL_PASSWORD`: Password for application database user
- `VIDEO_CUT_DASHSCOPE_API_KEY`: Your DashScope API key

### 3. Initialize Database

The MySQL database will be automatically initialized on first run. No manual steps required.

### 4. Start Services

```bash
# Build and start all services
docker-compose up -d

# Check if services are running
docker-compose ps

# View logs
docker-compose logs -f app
```

Services available at:
- **Application**: http://localhost:8462
- **MySQL**: localhost:3310 (external access)
- **Redis**: localhost:6379 (external access)

### 5. First Login

Default admin credentials (created automatically):
- **Username**: `admin`
- **Password**: `admin123`

⚠️ **IMPORTANT**: Change the default admin password immediately after first login!

## 📦 Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  Docker Network                      │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐  │
│  │  Nginx   │───▶│   App    │───▶│    MySQL     │  │
│  │ (Proxy)  │    │(FastAPI) │    │  (Database)  │  │
│  └──────────┘    └──────────┘    └──────────────┘  │
│                                    ┌──────────────┐  │
│                                    │    Redis     │  │
│                                    │   (Cache)    │  │
│                                    └──────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Services:**
- **app**: FastAPI application with user authentication
- **mysql**: MySQL 8.0 database for persistent storage
- **redis**: Redis cache (optional, for future features)
- **nginx**: Reverse proxy with SSL/TLS support (optional profile)

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `APP_PORT` | Application port | 8462 | No |
| `MYSQL_ROOT_PASSWORD` | MySQL root password | ChangeMe123!_Root | **Yes** |
| `MYSQL_DATABASE` | Database name | video_cut | No |
| `MYSQL_USER` | Database user | videocut | No |
| `MYSQL_PASSWORD` | Database user password | ChangeMe123!_User | **Yes** |
| `JWT_SECRET_KEY` | JWT signing key | (generate one) | **Yes** |
| `VIDEO_CUT_DASHSCOPE_API_KEY` | DashScope API key | (your key) | **Yes** |

### Resource Limits

Default resource allocations in `docker-compose.yml`:

```yaml
# MySQL
limits:
  memory: 1G
  cpus: '1.0'

# App
limits:
  memory: 4G
  cpus: '2.0'

# Redis
limits:
  memory: 256M
  cpus: '0.5'
```

Adjust based on your workload.

## 🗄️ Data Persistence

Data is stored in Docker volumes:

- `mysql_data`: MySQL database files
- `redis_data`: Redis persistence
- `app_data`: Uploaded videos and metadata
- `app_output`: Generated clips and processed videos
- `app_logs`: Application logs

**Backup example:**
```bash
# Backup MySQL database
docker-compose exec mysql mysqldump -u root -p video_cut > backup.sql

# Backup uploaded videos
docker run --rm -v video-cut_app_data:/data -v $(pwd):/backup alpine tar czf /backup/app_data.tar.gz /data
```

## 🔐 Security Best Practices

### 1. Change Default Passwords

```bash
# Generate strong passwords
openssl rand -base64 32  # For passwords
openssl rand -hex 32     # For JWT secret
```

### 2. Use HTTPS in Production

Enable the Nginx production profile with SSL:

```bash
# Place SSL certificates in deploy/nginx/ssl/
# fullchain.pem and privkey.pem

# Start with production profile
docker-compose --profile production up -d
```

### 3. Network Security

- Database is only accessible within Docker network
- External access via port 3310 (change in production)
- Use strong firewall rules

### 4. Regular Updates

```bash
# Update images
docker-compose pull
docker-compose up -d --build
```

## 🛠️ Management Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f mysql

# Last 100 lines
docker-compose logs --tail=100 app
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart app
```

### Stop Services

```bash
# Stop all (preserves data)
docker-compose down

# Stop and remove volumes (DELETES DATA!)
docker-compose down -v
```

### Execute Commands in Container

```bash
# Access app container shell
docker-compose exec app bash

# Access MySQL shell
docker-compose exec mysql mysql -u videocut -p video_cut

# Run Python commands
docker-compose exec app python -c "import sys; print(sys.version)"
```

## 🐛 Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs app

# Common issues:
# 1. Port already in use
sudo lsof -i :8462
sudo lsof -i :3310

# 2. Insufficient permissions
chmod 600 .env

# 3. Invalid environment variables
docker-compose config  # Validate compose file
```

### Database Connection Issues

```bash
# Check MySQL is running
docker-compose ps mysql

# Test connection
docker-compose exec app python -c "
import os
from sqlalchemy import create_engine
engine = create_engine(os.getenv('VIDEO_CUT_DATABASE_URL'))
print(engine.connect())
"

# Reset database (WARNING: Deletes all data!)
docker-compose down -v
docker-compose up -d
```

### Out of Memory

```bash
# Check resource usage
docker stats

# Adjust limits in docker-compose.yml
# Then restart
docker-compose up -d
```

### Clear Cache and Rebuild

```bash
docker-compose down
docker system prune -a
docker-compose build --no-cache
docker-compose up -d
```

## 📊 Monitoring

### Health Checks

All services have health checks configured:

```bash
# Check service health
docker inspect --format='{{.State.Health.Status}}' video-cut-app

# View health check logs
docker inspect --format='{{json .State.Health}}' video-cut-app | jq
```

### Resource Monitoring

```bash
# Real-time stats
docker stats video-cut-app video-cut-mysql video-cut-redis

# Disk usage
docker system df
```

## 🔄 CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Docker
        uses: docker/setup-buildx-action@v2

      - name: Deploy
        env:
          JWT_SECRET_KEY: ${{ secrets.JWT_SECRET_KEY }}
          MYSQL_PASSWORD: ${{ secrets.MYSQL_PASSWORD }}
        run: |
          docker-compose pull
          docker-compose up -d --build
          docker-compose exec app python src/video_cut/db/init_db.py
```

## 📝 Migration from Non-Docker

If you're migrating from a local installation:

### 1. Backup Existing Data

```bash
# Export MySQL database
mysqldump -u root -p video_cut > backup.sql

# Copy video files
tar czf videos.tar.gz output/ data/
```

### 2. Transfer to Docker Volume

```bash
# Import database
docker-compose exec -T mysql mysql -u root -p$MYSQL_ROOT_PASSWORD video_cut < backup.sql

# Restore files
docker run --rm -i -v video-cut_app_data:/data alpine tar xzf - < videos.tar.gz
```

## 🎯 Next Steps

1. ✅ Deploy application
2. ⬜ Configure SSL/TLS certificate
3. ⬜ Set up automated backups (cron job)
4. ⬜ Configure monitoring (Prometheus/Grafana)
5. ⬜ Set up log aggregation (ELK stack)
6. ⬜ Enable rate limiting and WAF

## 💡 Tips

- **Development**: Use `docker-compose logs -f` to watch logs in real-time
- **Production**: Always use `--profile production` for Nginx with HTTPS
- **Performance**: Allocate more resources to `app` service for video processing
- **Security**: Rotate passwords regularly and use `.env` file with restricted permissions

## 🆘 Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Verify environment: `docker-compose config`
3. Review this guide and troubleshooting section
4. Open an issue on the repository

---

**Happy Deploying! 🚀**
