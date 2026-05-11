"""从备份 SQLite 恢复 target_config / target_values 到当前数据库。

用法:
    python3 restore_targets.py /path/to/backup.db /path/to/current.db
"""
import sqlite3
import sys

if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <backup_db> <current_db>")
    sys.exit(1)

backup_path = sys.argv[1]
current_path = sys.argv[2]

src = sqlite3.connect(backup_path)
dst = sqlite3.connect(current_path)
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
        print(f'{table}: {len(rows)} rows restored')

dst.commit()
src.close()
dst.close()
print(f'Total: {total} target rows restored')
