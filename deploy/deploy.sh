#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/business-analysis}"
SERVICE_NAME="${SERVICE_NAME:-business-analysis}"
RUN_USER="${RUN_USER:-www-data}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/business-analysis-backups}"
DATA_DIR="${DATA_DIR:-/var/lib/business-analysis}"
LOG_DIR="${BUSINESS_ANALYSIS_LOG_DIR:-/var/log/business-analysis}"
DB_PATH="${BUSINESS_ANALYSIS_DB:-$DATA_DIR/business_data.db}"
LEGACY_DB_PATH="$APP_DIR/backend/business_data.db"
export BUSINESS_ANALYSIS_DB="$DB_PATH"
export BUSINESS_ANALYSIS_LOG_DIR="$LOG_DIR"
# auto: 首次部署且存在足够 Excel 时才全量重建；已有生产库默认保护页面上传数据。
REBUILD_DATABASE="${REBUILD_DATABASE:-auto}"
# auto: 只有本次新增迁移明确标记需要聚合重建时才执行；1 可强制重建。
REBUILD_AGGREGATES="${REBUILD_AGGREGATES:-auto}"
BACKUP_RESERVE_BYTES="${BACKUP_RESERVE_BYTES:-2147483648}"
RELEASE_ID="$(date +%Y%m%d_%H%M%S)-$$"
RELEASE_DIR="$BACKUP_DIR/release-$RELEASE_ID"
RECOVERY_TOOL="$SRC_DIR/deploy/release_recovery.py"

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo 运行 deploy/deploy.sh"
  exit 1
fi

REQUIRED_PACKAGES=(python3 python3-venv python3-pip nginx rsync)
MISSING_PACKAGES=()
for package in "${REQUIRED_PACKAGES[@]}"; do
  if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
    MISSING_PACKAGES+=("$package")
  fi
done
if [ "${#MISSING_PACKAGES[@]}" -gt 0 ]; then
  echo "安装缺失的系统依赖: ${MISSING_PACKAGES[*]}"
  apt-get update
  apt-get install -y "${MISSING_PACKAGES[@]}"
else
  echo "系统依赖已满足，跳过 apt 更新。"
fi

PYTHON_VERSION_OK=$(python3 - <<'PY'
import sys
print("1" if sys.version_info >= (3, 10) else "0")
PY
)
if [ "$PYTHON_VERSION_OK" != "1" ]; then
  echo "ERROR: Python 3.10+ is required. Current version: $(python3 --version 2>&1)"
  echo "Please install Python 3.10 or newer before running this deploy script."
  exit 1
fi

mkdir -p "$APP_DIR" "$BACKUP_DIR" "$DATA_DIR" "$LOG_DIR"
# Serialize releases. This lock is independent of application import locking.
exec 9>"$BACKUP_DIR/.deployment.lock"
chmod 600 "$BACKUP_DIR/.deployment.lock"
flock -n 9 || { echo "ERROR: another deployment or acceptance is running" >&2; exit 1; }
export BUSINESS_ANALYSIS_DEPLOY_LOCK_FD=9
if [ "$(realpath "$SRC_DIR")" = "$(realpath "$APP_DIR")" ]; then
  echo "ERROR: deployment requires a separate trusted release source" >&2
  exit 1
fi

# 自动部署链路曾允许 www-data 执行项目树内可写脚本。正式安全方案落地前关闭该链路，
# 仅保留由管理员通过可信发布包手工执行本脚本的方式。
systemctl disable --now webhook-deploy 2>/dev/null || true
rm -f /etc/sudoers.d/webhook-deploy

SERVICE_WAS_ACTIVE=0
if systemctl is-active --quiet "$SERVICE_NAME"; then
  SERVICE_WAS_ACTIVE=1
fi

SERVICE_STOPPED=0
STAGED_VENV=""
PREVIOUS_VENV=""
VENV_SWAPPED=0
MIGRATION_SNAPSHOT=""
RECOVERY_MUTATED=0
CANDIDATE_STARTED=0

restore_service_on_error() {
  local exit_code="${1:-$?}"
  trap - ERR
  set +e
  echo "ERROR: 部署中止；恢复材料: $RELEASE_DIR" >&2
  if [ "$RECOVERY_MUTATED" = "1" ]; then
    systemctl stop -- "$SERVICE_NAME"
    if [ "$CANDIDATE_STARTED" = "1" ]; then
      python3 "$RECOVERY_TOOL" mark --release-dir "$RELEASE_DIR" --state blocked
      echo "ERROR: 新版本已启动，无法证明无新增写入；自动代码/数据库回退已拒绝，服务保持停止。" >&2
      echo "检查新写入与迁移兼容性后，使用 release_recovery.py restore --release-dir '$RELEASE_DIR' --confirm-no-new-writes；不得未经复核直接覆盖数据库。" >&2
      exit "$exit_code"
    fi
    if ! python3 "$RECOVERY_TOOL" restore --release-dir "$RELEASE_DIR"; then
      echo "ERROR: 恢复未完成，服务保持停止。请检查恢复材料，不要删除任何备份。" >&2
      exit "$exit_code"
    fi
    chown -R root:root "$APP_DIR"
    chmod 755 "$APP_DIR"
    if [ -f "$DB_PATH" ]; then
      chown "$RUN_USER:$RUN_USER" "$DB_PATH"
      chmod 640 "$DB_PATH"
    fi
    systemctl daemon-reload
    nginx -t && systemctl reload nginx
  fi
  if [ "$SERVICE_WAS_ACTIVE" = "1" ] && [ "$SERVICE_STOPPED" = "1" ]; then
    systemctl start "$SERVICE_NAME" 2>/dev/null || true
  fi
  exit "$exit_code"
}
trap restore_service_on_error ERR

cleanup_deploy_temps() {
  if [ -n "$STAGED_VENV" ] && [ -d "$STAGED_VENV" ]; then
    rm -rf "$STAGED_VENV"
  fi
  if [ -n "$MIGRATION_SNAPSHOT" ] && [ -f "$MIGRATION_SNAPSHOT" ]; then
    rm -f "$MIGRATION_SNAPSHOT"
  fi
}
trap cleanup_deploy_temps EXIT

# 首次切换到专用运行数据目录时，使用 SQLite Online Backup API 迁移旧运行库。
if [ ! -f "$DB_PATH" ] && [ -f "$LEGACY_DB_PATH" ]; then
  python3 "$SRC_DIR/deploy/backup_policy.py" --database "$LEGACY_DB_PATH" \
    --backup-dir "$DATA_DIR" --copies 1 --reserve-bytes "$BACKUP_RESERVE_BYTES"
  echo "正在将生产数据库迁移到独立数据目录: $DB_PATH"
  python3 "$SRC_DIR/backend/backup_database.py" \
    --source "$LEGACY_DB_PATH" \
    --destination "$DB_PATH"
fi

DB_EXISTED_BEFORE=0
if [ -f "$DB_PATH" ]; then
  DB_EXISTED_BEFORE=1
fi
# Reserve for both the online safety copy and the final frozen recovery point.
python3 "$SRC_DIR/deploy/backup_policy.py" --database "$DB_PATH" \
  --backup-dir "$BACKUP_DIR" --copies 2 --reserve-bytes "$BACKUP_RESERVE_BYTES"
# 只要生产数据库存在就备份，避免有经营数据/权限数据但目标配置为空时漏备份。
if [ -f "$DB_PATH" ]; then
  BACKUP_TS="$RELEASE_ID"
  BACKUP_FILE="$BACKUP_DIR/business_data.db.$BACKUP_TS"
  python3 "$SRC_DIR/backend/backup_database.py" \
    --source "$DB_PATH" \
    --destination "$BACKUP_FILE" \
    --meta "$BACKUP_FILE.meta"
  echo "已备份数据库: $BACKUP_FILE"
fi

python3 "$RECOVERY_TOOL" capture --app-dir "$APP_DIR" --release-dir "$RELEASE_DIR" \
  --database "$DB_PATH" --service "$SERVICE_NAME" \
  --config "/etc/systemd/system/${SERVICE_NAME}.service" \
  --config /etc/nginx/sites-available/business-analysis \
  --config /etc/nginx/sites-enabled/business-analysis \
  --config /etc/nginx/sites-enabled/default
RECOVERY_TOOL="$RELEASE_DIR/recovery-tools/release_recovery.py"
DEPLOY_REBUILD_LOCK="$RELEASE_DIR/deployment-operation.lock"

# 在服务仍在线时记录迁移基线；init_db后只对本次新增且明确要求的迁移重建聚合。
MIGRATION_SNAPSHOT="$(mktemp)"
python3 "$SRC_DIR/deploy/deployment_plan.py" snapshot \
  --database "$DB_PATH" > "$MIGRATION_SNAPSHOT"

# requirements未变化且现有环境自检通过时复用venv；否则先在线构建候选环境，
# 避免下载依赖占用主服务停机窗口。
REUSE_EXISTING_VENV=0
if [ -x "$APP_DIR/backend/venv/bin/python" ] \
  && [ -f "$APP_DIR/backend/requirements.txt" ] \
  && cmp -s "$SRC_DIR/backend/requirements.txt" "$APP_DIR/backend/requirements.txt" \
  && "$APP_DIR/backend/venv/bin/python" -m pip check >/dev/null 2>&1; then
  REUSE_EXISTING_VENV=1
  echo "Python依赖未变化且环境自检通过，复用现有venv。"
else
  STAGED_VENV="$APP_DIR/backend/venv.next.$RELEASE_ID"
  if [ -e "$STAGED_VENV" ]; then
    echo "ERROR: candidate dependency path already exists; refusing overwrite" >&2
    STAGED_VENV=""
    false
  fi
  python3 -m venv "$STAGED_VENV"
  "$STAGED_VENV/bin/pip" install --upgrade pip
  "$STAGED_VENV/bin/pip" install -r "$SRC_DIR/backend/requirements.txt"
  "$STAGED_VENV/bin/python" -m pip check
  echo "候选Python环境已在线准备完成。"
fi

# 备份、依赖检查和候选环境准备均已完成，从这里才进入短维护窗口。
# Honor the same flock as API imports and maintenance rebuild scripts.
IMPORT_LOCK_PATH="${BUSINESS_ANALYSIS_LOCK:-}"
if [ -z "$IMPORT_LOCK_PATH" ]; then
  IMPORT_LOCK_PATH="$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).with_suffix(".import.lock"))' "$DB_PATH")"
fi
exec 8>"$IMPORT_LOCK_PATH"
chown "$RUN_USER:$RUN_USER" "$IMPORT_LOCK_PATH"
chmod 660 "$IMPORT_LOCK_PATH"
flock -n 8 || { echo "ERROR: a database import/rebuild is running; deployment stopped" >&2; false; }
export BUSINESS_ANALYSIS_IMPORT_LOCK_FD=8
if [ "$SERVICE_WAS_ACTIVE" = "1" ]; then
  systemctl stop "$SERVICE_NAME"
  SERVICE_STOPPED=1
fi

# Stop-time snapshot contains every commit made after the initial online backup.
# Never restore the earlier online copy over this final maintenance point.
python3 "$SRC_DIR/deploy/backup_policy.py" --database "$DB_PATH" \
  --backup-dir "$BACKUP_DIR" --copies 1 --reserve-bytes "$BACKUP_RESERVE_BYTES"
python3 "$RECOVERY_TOOL" freeze --release-dir "$RELEASE_DIR" \
  --destination "$BACKUP_DIR/business_data.db.$RELEASE_ID.frozen"
python3 "$RECOVERY_TOOL" mark --release-dir "$RELEASE_DIR" --state mutating
RECOVERY_MUTATED=1

rsync -a --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='backend/__pycache__' \
  --exclude='backend/venv*' \
  --exclude='backend/logs/*.log' \
  --exclude='deploy/.admin_env' \
  --exclude='deploy/.ai_env' \
  --exclude='deploy/.webhook_env' \
  --exclude='*.xlsx' \
  --exclude='*.db' \
  "$SRC_DIR/" "$APP_DIR/"

if [ "$REUSE_EXISTING_VENV" = "0" ]; then
  PREVIOUS_VENV="$APP_DIR/backend/venv.previous.$RELEASE_ID"
  if [ -e "$PREVIOUS_VENV" ]; then
    echo "ERROR: preserved dependency path already exists; refusing overwrite" >&2
    false
  fi
  python3 "$RECOVERY_TOOL" mark --release-dir "$RELEASE_DIR" --state mutating --previous-venv "$PREVIOUS_VENV"
  if [ -d "$APP_DIR/backend/venv" ]; then
    mv "$APP_DIR/backend/venv" "$PREVIOUS_VENV"
  fi
  mv "$STAGED_VENV" "$APP_DIR/backend/venv"
  STAGED_VENV=""
  VENV_SWAPPED=1
fi

cd "$APP_DIR/backend"
"$APP_DIR/backend/venv/bin/python" -c "from db import init_db; init_db()"

# 从所有备份中自动找出目标数据最多的那个恢复
bash "$APP_DIR/deploy/recover_targets.sh" || echo '⚠ 目标数据恢复失败，请检查备份目录'

# 如果备份恢复后仍无目标数据，从 targets_import.json 导入（Excel 解析的预设目标）
if [ -f "$APP_DIR/targets_import.json" ]; then
  HAS_TARGETS=$("$APP_DIR/backend/venv/bin/python" -c "
import sqlite3, json, os
db='$DB_PATH'
if os.path.exists(db):
    c=sqlite3.connect(db)
    n=c.execute('SELECT COUNT(*) FROM target_config').fetchone()[0]
    c.close()
    print(n)
else:
    print(0)
" 2>/dev/null || echo "0")
  if [ "$HAS_TARGETS" = "0" ]; then
    echo "从 targets_import.json 导入预设目标..."
    "$APP_DIR/backend/venv/bin/python" -c "
import json, sys
sys.path.insert(0, '$APP_DIR/backend')
from db import save_target_config
with open('$APP_DIR/targets_import.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
result = save_target_config(data['year'], data, updated_by='deploy')
print(f'已导入 {data[\"year\"]} 年目标配置')
" && echo '✓ 预设目标导入成功' || echo '⚠ 预设目标导入失败'
  fi
fi

# 数据刷新策略：
# - 默认auto：已有生产库不使用旧Excel，且只有本次新增迁移明确要求时才重建聚合；
# - REBUILD_DATABASE=1：以完整Excel源全量重建；
# - REBUILD_AGGREGATES=1：保留现有库但强制从原始表重建聚合；
# - 即使设置REBUILD_AGGREGATES=0，新出现的强制迁移仍会优先触发重建。
EXCEL_COUNT=$(find "$APP_DIR" -maxdepth 1 -name "*.xlsx" 2>/dev/null | wc -l)
PLAN_TEXT="$("$APP_DIR/backend/venv/bin/python" "$APP_DIR/deploy/deployment_plan.py" plan \
  --database "$DB_PATH" \
  --snapshot "$MIGRATION_SNAPSHOT" \
  --database-existed "$DB_EXISTED_BEFORE" \
  --excel-count "$EXCEL_COUNT" \
  --rebuild-database "$REBUILD_DATABASE" \
  --rebuild-aggregates "$REBUILD_AGGREGATES" \
  --format lines)"
mapfile -t PLAN_LINES <<< "$PLAN_TEXT"
if [ "${#PLAN_LINES[@]}" -lt 4 ]; then
  echo "ERROR: 无法生成完整的数据刷新计划。" >&2
  false
fi
SHOULD_REBUILD_FROM_EXCEL="${PLAN_LINES[0]}"
SHOULD_REBUILD_AGGREGATES="${PLAN_LINES[1]}"
NEW_REQUIRED_MIGRATIONS="${PLAN_LINES[2]}"
DEPLOY_PLAN_REASON="${PLAN_LINES[3]}"
echo "数据刷新计划: $DEPLOY_PLAN_REASON"
if [ "$NEW_REQUIRED_MIGRATIONS" != "-" ]; then
  echo "新增的强制聚合迁移: $NEW_REQUIRED_MIGRATIONS"
fi

if [ "$SHOULD_REBUILD_FROM_EXCEL" = "1" ]; then
  echo "检测到 $EXCEL_COUNT 个 Excel 文件，正在重建数据库..."
  # The outer import flock remains held by this deployment. The subprocess uses
  # a private nested lock, so external writers stay blocked without self-deadlock.
  BUSINESS_ANALYSIS_LOCK="$DEPLOY_REBUILD_LOCK" "$APP_DIR/backend/venv/bin/python" "$APP_DIR/backend/rebuild_from_excels.py" || {
    echo "ERROR: 数据库重建失败，部署已中止。请检查 Excel 文件名、字段和重建日志。"
    restore_service_on_error 1
  }
elif [ "$SHOULD_REBUILD_AGGREGATES" = "1" ]; then
  if [ "$DB_EXISTED_BEFORE" = "1" ]; then
    echo "检测到已有生产数据库，默认不从 Excel 全量重建；如需强制重建请设置 REBUILD_DATABASE=1"
  fi
  REBUILD_SCOPE="$("$APP_DIR/backend/venv/bin/python" "$APP_DIR/deploy/deployment_plan.py" plan \
    --database "$DB_PATH" --snapshot "$MIGRATION_SNAPSHOT" \
    --database-existed "$DB_EXISTED_BEFORE" --excel-count "$EXCEL_COUNT" \
    --rebuild-database "$REBUILD_DATABASE" --rebuild-aggregates "$REBUILD_AGGREGATES" \
    --format scope)"
  case "$REBUILD_SCOPE" in
    customer_facts)
      echo "本次强制迁移仅涉及客户事实，正在单独重建客户事实及索引..."
      BUSINESS_ANALYSIS_LOCK="$DEPLOY_REBUILD_LOCK" "$APP_DIR/backend/venv/bin/python" "$APP_DIR/backend/rebuild_customer_facts.py" || {
        echo "ERROR: 客户事实重建失败，部署已中止。" >&2
        restore_service_on_error 1
      }
      ;;
    full)
      echo "正在从SQLite原始明细表重建聚合..."
      BUSINESS_ANALYSIS_LOCK="$DEPLOY_REBUILD_LOCK" "$APP_DIR/backend/venv/bin/python" "$APP_DIR/backend/rebuild_aggregates_from_raw_tables.py" || {
        echo "ERROR: SQLite 原始表重建失败，部署已中止，避免以空聚合或旧聚合继续上线。" >&2
        restore_service_on_error 1
      }
      ;;
    *)
      echo "ERROR: 强制重建迁移没有有效的执行范围，部署已中止。" >&2
      restore_service_on_error 1
      ;;
  esac
else
  echo "保留现有生产库及聚合结果，跳过耗时的全量聚合重建。"
fi

echo "Account auth enabled; ADMIN_TOKEN is no longer required."

cp "$APP_DIR/deploy/systemd.service" "/etc/systemd/system/${SERVICE_NAME}.service"
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/business-analysis
ln -sf /etc/nginx/sites-available/business-analysis /etc/nginx/sites-enabled/business-analysis
rm -f /etc/nginx/sites-enabled/default

# 验证 nginx 配置（client_max_body_size 必须包含）
if ! grep -q "client_max_body_size" /etc/nginx/sites-available/business-analysis; then
  echo "⚠ 警告：nginx 配置缺少 client_max_body_size，大文件上传将被拒绝（413 错误）"
fi

# 应用代码只读；仅独立的数据目录和日志目录允许应用账号写入。
chown -R root:root "$APP_DIR"
# rsync 会继承可信发布包解压目录的根目录权限；mktemp 默认为 0700，
# 必须显式恢复应用根目录的可遍历权限，否则 www-data 无法进入 WorkingDirectory。
chmod 755 "$APP_DIR"
chown -R "$RUN_USER:$RUN_USER" "$DATA_DIR" "$LOG_DIR"
chmod 750 "$DATA_DIR" "$LOG_DIR"
if [ -f "$DB_PATH" ]; then
  chmod 640 "$DB_PATH"
fi
for runtime_env in "$APP_DIR/deploy/.admin_env" "$APP_DIR/deploy/.ai_env" "$APP_DIR/deploy/.webhook_env"; do
  if [ -f "$runtime_env" ]; then
    chown root:"$RUN_USER" "$runtime_env"
    chmod 640 "$runtime_env"
  fi
done

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
python3 "$RECOVERY_TOOL" mark --release-dir "$RELEASE_DIR" --state started
CANDIDATE_STARTED=1
systemctl restart "$SERVICE_NAME"
nginx -t && systemctl reload nginx

HEALTH_OK=0
for _attempt in $(seq 1 30); do
  if "$APP_DIR/backend/venv/bin/python" - <<'PY'
from urllib.request import urlopen
import json

with urlopen("http://127.0.0.1:45679/api/health", timeout=2) as response:
    if response.status != 200 or json.load(response).get("status") != "ok":
        raise SystemExit(1)
PY
  then
    HEALTH_OK=1
    break
  fi
  sleep 1
done
if [ "$HEALTH_OK" != "1" ]; then
  echo "ERROR: 主服务启动后30秒内未通过健康检查。" >&2
  false
fi
echo "主服务健康检查通过。"
SERVICE_STOPPED=0
python3 "$RECOVERY_TOOL" mark --release-dir "$RELEASE_DIR" --state healthy
# Keep the old code, dependency environment and all backup points until the
# operator has completed formal HTTPS, permissions and business-data acceptance.
echo "完整上线复核通过后执行（保留本次冻结备份和一套恢复包）:"
echo "sudo python3 '$RECOVERY_TOOL' accept-release --release-dir '$RELEASE_DIR' --confirm-review-complete"

# 主服务恢复后再同步独立的市场研判单元，避免该附属步骤延长看板停机窗口。
if command -v claude >/dev/null 2>&1 || [ -x /usr/local/bin/claude ]; then
  bash "$APP_DIR/deploy/install-market-analysis.sh" --skip-cli-install || \
    echo "⚠ 市场研判服务同步失败，经营看板继续运行；请单独检查 install-market-analysis.sh"
else
  echo "⚠ 尚未安装 Claude Code CLI；市场研判页面可用，但定时研究尚未启用"
fi

trap - ERR
APP_VERSION=$(grep -oP 'v\d+\.\d+\.\d+' "$APP_DIR/经营分析模板.html" | head -1 || true)

echo ""
echo "============================================"
echo "  代码部署及本机健康检查完成（待完整上线验收）"
echo "  访问地址: http://<服务器IP>/"
echo "  版本: ${APP_VERSION:-unknown}"
echo ""
echo "  自动部署: 已因安全整改暂停；请使用可信发布包手工执行 deploy/deploy.sh"
echo "============================================"
echo "  默认管理员账号: admin"
