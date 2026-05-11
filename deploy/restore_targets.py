"""从备份目录中找到含最多目标数据的备份，恢复到当前数据库。

用法:
    python3 restore_targets.py /path/to/backup_dir /path/to/current.db
"""
import os
import sqlite3
import sys


def count_target_rows(db_path):
    """返回 (target_config_rows, target_values_rows)，数据库不存在则返回 (0, 0)。"""
    if not os.path.exists(db_path):
        return (0, 0)
    try:
        conn = sqlite3.connect(db_path)
        c1 = conn.execute('SELECT COUNT(*) FROM target_config').fetchone()[0]
        c2 = conn.execute('SELECT COUNT(*) FROM target_values').fetchone()[0]
        conn.close()
        return (c1, c2)
    except Exception:
        return (0, 0)


def restore_from(src_path, dst_path):
    """从 src_path 复制 target_config / target_values 到 dst_path。"""
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
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
            print(f'  {table}: {len(rows)} rows')

    dst.commit()
    src.close()
    dst.close()
    return total


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <backup_dir> <current_db>")
        sys.exit(1)

    backup_dir = sys.argv[1]
    current_db = sys.argv[2]

    # 收集所有备份文件及其目标数据行数
    backups = []
    if os.path.isdir(backup_dir):
        for f in sorted(os.listdir(backup_dir)):
            if f.startswith('business_data.db.'):
                path = os.path.join(backup_dir, f)
                cfg, val = count_target_rows(path)
                if cfg > 0 or val > 0:
                    backups.append((cfg + val, cfg, val, path))

    if not backups:
        print('No backups with target data found — skipping restore')
        sys.exit(0)

    # 选目标数据最多的备份
    backups.sort(reverse=True)
    total_rows, cfg_count, val_count, best_path = backups[0]
    print(f'Best backup: {os.path.basename(best_path)} '
          f'(target_config={cfg_count}, target_values={val_count})')

    # 检查当前数据库是否已有数据
    cur_cfg, cur_val = count_target_rows(current_db)
    if cur_cfg + cur_val >= total_rows:
        print(f'Current db already has {cur_cfg + cur_val} target rows, >= backup ({total_rows}) — skipping')
        sys.exit(0)

    restored = restore_from(best_path, current_db)
    print(f'Restored {restored} target rows from {os.path.basename(best_path)}')
