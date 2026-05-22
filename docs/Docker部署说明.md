# Docker 部署说明

## 概述

本项目提供两种方式部署 Docker 容器：

| 方式 | 适用场景 | 说明 |
|------|----------|------|
| **方式一：自带 nginx（推荐新手）** | 服务器没有现成反向代理 | docker-compose 内置 nginx，开箱即用 |
| **方式二：外部反向代理** | 已有 Nginx Proxy Manager 等 | 容器直接暴露端口，由外部代理接管 |

## 方式一：自带 nginx（推荐）

使用内置 nginx，已配置好 `client_max_body_size 100m`，无需额外操作：

```bash
# 使用含 nginx 的 compose 文件
docker compose -f docker-compose.yml -f docker-compose.nginx.yml up -d
```

访问 `http://<服务器IP>` 即可。

## 方式二：外部反向代理（如 Nginx Proxy Manager）

如果已有外部反向代理，使用标准 compose 文件：

```bash
docker compose up -d
```

### 关键配置：client_max_body_size

**上传 4 份 Excel 合计约 16MB，反向代理默认限制仅 1MB，会导致 413 错误。**

#### Nginx Proxy Manager 配置

1. 打开 NPM 管理界面 → 选择对应 Proxy Host → Edit
2. 切换到 **Advanced** 标签
3. 在 Custom Nginx Configuration 中填入：

```nginx
client_max_body_size 100m;
```

4. Save

#### 原生 nginx 配置

在 `server` 块中加入：

```nginx
server {
    listen 80;
    # ... 其他配置 ...
    client_max_body_size 100m;

    location /api/ {
        proxy_pass http://<宿主机IP>:45679;
        # ...
    }
}
```

## 从 GitHub Container Registry 拉取镜像

镜像已自动构建并推送至 GitHub Container Registry，无需本地构建：

```bash
# 登录 GitHub Container Registry
echo $CR_PAT | docker login ghcr.io -u <你的GitHub用户名> --password-stdin

# 直接拉取运行
docker pull ghcr.io/<用户名>/<仓库名>:master
docker run -d -p 45679:45679 ghcr.io/<用户名>/<仓库名>:master
```

> **注意**：需要先在 GitHub 个人设置中生成 Personal Access Token（`read:packages` 权限），作为 `CR_PAT`。

### 使用预构建镜像的 docker-compose

```yaml
services:
  app:
    image: ghcr.io/<用户名>/<仓库名>:master
    container_name: business-analysis
    ports:
      - "45679:45679"
    volumes:
      - ./backend/business_data.db:/app/backend/business_data.db
      - ./backend/logs:/app/backend/logs
    environment:
      - APP_ENV=production
      - ADMIN_TOKEN=${ADMIN_TOKEN:-Aaaaa8888%}
    restart: unless-stopped
```

## 数据持久化

| 路径 | 说明 | 是否必须 |
|------|------|----------|
| `./backend/business_data.db` | SQLite 数据库文件，与程序运行库路径保持一致 | 是 |
| `./backend/logs` | 应用日志目录 | 否 |
| `./targets_import.json` | 目标配置（只读挂载） | 否 |

## 常用命令

```bash
# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 进入容器调试
docker compose exec app bash

# 停止并删除容器
docker compose down

# 更新镜像（拉取最新）
docker compose pull && docker compose up -d
```

## 故障排查

### 413 Request Entity Too Large

**原因**：反向代理的 `client_max_body_size` 未配置或配置过小。

**解决**：
- 方式一：使用自带 nginx 的 compose 文件，已内置配置
- 方式二：在外部反向代理中设置 `client_max_body_size 100m`

### 数据库初始化失败

**原因**：宿主机 `backend/business_data.db` 不存在时，Docker bind mount 可能创建目录而非文件。

**解决**：`docker-entrypoint.sh` 已自动处理此情况，会删除目录占位符并重新初始化数据库。
