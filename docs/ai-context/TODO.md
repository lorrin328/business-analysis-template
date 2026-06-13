# TODO

## P1

- 推送到 GitHub 后检查 Actions `Build Docker image` 是否成功。
- 在 GitHub Packages/GHCR 中确认 `ghcr.io/lorrin328/business-analysis-template:latest` 已生成。
- 在目标 Ubuntu/NAS 机器上执行一次 `docker pull` 和 `docker run` 冒烟验证。

## P2

- 按生产访问方式补充 nginx 反向代理到 Docker 容器的正式配置。
- 明确容器部署时 `.env` 示例文件，记录必要但不含真实值的环境变量。
- 根据是否多人访问，补充备份和恢复脚本，重点覆盖 `/data/business_data.db`。
