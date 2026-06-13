# Docker deployment

This project can be built and published as a deployable Docker image.

## Image

GitHub Actions publishes the image to GitHub Container Registry:

```bash
ghcr.io/lorrin328/business-analysis-template:latest
```

Version tags are also published when a Git tag such as `v1.0.93` is pushed.

## Run from GHCR

```bash
docker pull ghcr.io/lorrin328/business-analysis-template:latest
docker run -d \
  --name business-analysis \
  --restart unless-stopped \
  -p 45679:45679 \
  -e APP_ENV=production \
  -e MAX_UPLOAD_SIZE_MB=100 \
  -e BUSINESS_ANALYSIS_DB=/data/business_data.db \
  -v business-analysis-data:/data \
  -v business-analysis-logs:/app/backend/logs \
  ghcr.io/lorrin328/business-analysis-template:latest
```

## Compose

```bash
docker compose up -d
```

## Runtime data

The image does not include Excel source files, SQLite runtime databases, logs, or secrets. Runtime data is stored in Docker volumes:

- `business-analysis-data`: SQLite database files.
- `business-analysis-logs`: application logs.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `PORT` | Uvicorn listen port inside the container. | `45679` |
| `BUSINESS_ANALYSIS_DB` | SQLite database path. | `/data/business_data.db` |
| `MAX_UPLOAD_SIZE_MB` | Upload size limit. | `100` in Compose |
| `CORS_ORIGINS` | Optional comma-separated allowed origins. | empty |
| `ADMIN_TOKEN` | Optional admin token if enabled by the app. | unset |
| `AI_READONLY_TOKEN` | Optional token for read-only AI APIs. | unset |

Secrets must be provided by `.env`, the server secret manager, or the container platform. Do not commit real tokens or passwords.

## Build locally

```bash
docker build -t business-analysis-template:local .
docker run --rm -p 45679:45679 -v business-analysis-data:/data business-analysis-template:local
```

Health check:

```bash
curl http://127.0.0.1:45679/api/health
```
