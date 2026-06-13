# DECISIONS

## 2026-06-13 容器镜像发布方式

- 决策：使用 GitHub Actions 构建镜像并推送到 GitHub Container Registry。
- 镜像名：`ghcr.io/lorrin328/business-analysis-template`。
- 原因：镜像二进制文件不适合直接提交到 Git 仓库；GHCR 支持 `latest`、分支、tag、sha 多维度版本管理，后续服务器可直接 `docker pull`。
- 约束：镜像不内置业务数据和真实密钥，SQLite 数据库、日志通过 volume 持久化。
