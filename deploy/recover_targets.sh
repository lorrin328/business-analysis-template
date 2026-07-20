#!/usr/bin/env bash
# 从备份目录中自动找出含目标数据的备份并恢复到当前数据库。
# 用法: sudo bash deploy/recover_targets.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/business-analysis}"
BACKUP_DIR="${BACKUP_DIR:-/opt/business-analysis-backups}"
DB="${BUSINESS_ANALYSIS_DB:-/var/lib/business-analysis/business_data.db}"

echo "=== 目标数据恢复 ==="
echo "数据库: $DB"
echo "备份目录: $BACKUP_DIR"

# 检查当前数据库的目标数据
CUR_TARGETS=$(python3 -c "
import sqlite3, os
if not os.path.exists('$DB'):
    print('NO_DB')
else:
    c = sqlite3.connect('$DB')
    n = c.execute('SELECT COUNT(*) FROM target_config').fetchone()[0]
    m = c.execute('SELECT COUNT(*) FROM target_values').fetchone()[0]
    c.close()
    print(f'{n},{m}')
" 2>/dev/null || echo "ERROR")

echo "当前数据库目标数据: $CUR_TARGETS"

# 如果当前数据库已有目标数据，无需恢复
if [ "$CUR_TARGETS" != "NO_DB" ] && [ "$CUR_TARGETS" != "ERROR" ] && [ "$CUR_TARGETS" != "0,0" ]; then
    echo "当前数据库已有目标数据，跳过恢复"
    exit 0
fi

# 扫描所有备份
echo ""
echo "扫描备份文件..."
BEST=""
BEST_COUNT=0
BEST_INFO=""

if [ -d "$BACKUP_DIR" ]; then
    for f in "$BACKUP_DIR"/business_data.db.*; do
        [ -f "$f" ] || continue
        INFO=$(python3 -c "
import sqlite3
c = sqlite3.connect('$f')
n = c.execute('SELECT COUNT(*) FROM target_config').fetchone()[0]
m = c.execute('SELECT COUNT(*) FROM target_values').fetchone()[0]
# 读取年份信息
years = ''
if n > 0:
    rows = c.execute('SELECT year FROM target_config ORDER BY year').fetchall()
    years = ','.join(str(r[0]) for r in rows)
c.close()
print(f'{n+m}|{n}|{m}|{years}')
" 2>/dev/null || echo "0|0|0|")
        TOTAL=$(echo "$INFO" | cut -d'|' -f1)
        CFG=$(echo "$INFO" | cut -d'|' -f2)
        VAL=$(echo "$INFO" | cut -d'|' -f3)
        YRS=$(echo "$INFO" | cut -d'|' -f4)
        FNAME=$(basename "$f")
        echo "  $FNAME: config=$CFG values=$VAL years=$YRS"
        if [ "$TOTAL" -gt "$BEST_COUNT" ] 2>/dev/null; then
            BEST_COUNT=$TOTAL
            BEST="$f"
            BEST_INFO="config=$CFG values=$VAL years=$YRS"
        fi
    done
fi

if [ -z "$BEST" ]; then
    echo ""
    echo "未找到任何含目标数据的备份"
    echo "如果之前手工录入过目标，请检查备份目录: $BACKUP_DIR"
    exit 1
fi

echo ""
echo "最佳备份: $(basename "$BEST") ($BEST_INFO)"
echo "正在恢复..."

python3 -c "
import sqlite3
src = sqlite3.connect('$BEST')
dst = sqlite3.connect('$DB')
total = 0
for table in ['target_config', 'target_values']:
    src.row_factory = sqlite3.Row
    rows = src.execute(f'SELECT * FROM {table}').fetchall()
    if rows:
        cols = [c[0] for c in src.execute(f'PRAGMA table_info({table})')]
        col_str = ','.join(cols)
        ph = ','.join(['?'] * len(cols))
        dst.executemany(
            f'INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({ph})',
            [tuple(r[c] for c in cols) for r in rows]
        )
        total += len(rows)
        print(f'  {table}: {len(rows)} rows restored')
dst.commit()
src.close()
dst.close()
print(f'恢复完成，共 {total} 条目标数据')
"

echo "=== 恢复成功 ==="
