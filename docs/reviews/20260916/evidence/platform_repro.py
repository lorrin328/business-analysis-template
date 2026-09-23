"""Read-only review probes. Synthetic in-memory data; no application init or production writes."""
import ast
import os
from pathlib import Path
import sqlite3
import sys
from contextlib import contextmanager

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'backend'))
import honor.repository as repo
from services.excel_exporter import _write_table
from openpyxl import Workbook
from auth import _test_bypass_enabled

conn = sqlite3.connect(':memory:')
conn.row_factory = sqlite3.Row
conn.execute('CREATE TABLE honor_person_month (id INTEGER PRIMARY KEY, batch_id INTEGER)')
conn.executemany('INSERT INTO honor_person_month(batch_id) VALUES (?)', [(1,)] * 5001)
@contextmanager
def fake_db():
    yield conn
repo.get_db = fake_db
rows = repo.fetch_table('honor_person_month', 1, limit=5000)
print('HONOR: synthetic source=5001; returned=' + str(len(rows)))
assert len(rows) == 5000

workbook = Workbook()
_write_table(workbook.active, 'synthetic', ['label'], [['=1+1']])
cell = workbook.active['A3']
print('EXCEL: synthetic label=' + repr(cell.value) + '; cell data_type=' + repr(cell.data_type))
assert cell.data_type == 'f'

# Evaluate the actual status expression extracted from source, not a duplicated formula.
tree = ast.parse((ROOT / 'backend/api/diagnostics.py').read_text(encoding='utf-8'))
status_expression = None
note = None
for node in ast.walk(tree):
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == 'status' and isinstance(value, ast.IfExp):
                status_expression = value
            if isinstance(key, ast.Constant) and key.value == 'note' and isinstance(value, ast.Constant):
                note = value.value
assert status_expression is not None and note
compiled = compile(ast.Expression(body=status_expression), '<actual-diagnostics-status>', 'eval')
for ratio in (90, 70):
    print('DIAGNOSTICS: ratio=' + str(ratio) + '; actual status=' + eval(compiled, {'ratio': ratio}))
print('DIAGNOSTICS: actual note=' + note)

# Only this process environment is modified and restored.
old = {k: os.environ.get(k) for k in ('APP_ENV', 'AUTH_TEST_BYPASS')}
try:
    os.environ['AUTH_TEST_BYPASS'] = '1'
    for app_env in ('production', 'staging', ''):
        if app_env:
            os.environ['APP_ENV'] = app_env
        else:
            os.environ.pop('APP_ENV', None)
        print('AUTH: AUTH_TEST_BYPASS=1; APP_ENV=' + repr(app_env) + '; bypass=' + str(_test_bypass_enabled()))
finally:
    for key, value in old.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
conn.close()
