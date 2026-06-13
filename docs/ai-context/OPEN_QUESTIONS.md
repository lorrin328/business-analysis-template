# OPEN_QUESTIONS

## 2026-06-13

- GHCR 镜像包是否需要公开访问，还是保持私有并由服务器使用 GitHub token 登录拉取。
- 生产环境是否继续保留 nginx 反向代理，或改为直接由 Docker Compose 暴露 `45679` 后再接入宿主机 nginx。
- 容器部署时管理员 Token、AI 只读 Token 等环境变量的正式命名和生成规则需按现有鉴权实现最终确认。
