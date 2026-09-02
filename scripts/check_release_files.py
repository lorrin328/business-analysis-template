"""Check tracked release content without printing any sensitive file contents."""
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {'.venv', 'venv', '__pycache__', 'node_modules', 'excel', 'backups', 'market_analysis_data'}


def disallowed(path: str) -> bool:
    p = PurePosixPath(path.replace("\\", "/").lower())
    return (
        bool(set(p.parts) & FORBIDDEN_PARTS)
        or any(part.startswith(('venv.', '.venv.')) for part in p.parts)
        or 'sync-conflict' in p.as_posix()
        or p.name.endswith(('.db', '.db-wal', '.db-shm', '.sqlite', '.sqlite-wal', '.sqlite-shm', '.sqlite3', '.sqlite3-wal', '.sqlite3-shm', '.xlsx', '.xls', '.xlsm', '.csv', '.log', '.pyc', '.pyo'))
        or (p.name.startswith('.env') and p.name != '.env.example')
        or p.name.endswith('_env')
    )


def main():
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    bad = [path for path in paths if path and disallowed(path)]
    if bad:
        raise SystemExit('Release contains forbidden data/runtime paths: ' + ', '.join(bad))
    print('Tracked release file boundary: ok')


if __name__ == '__main__':
    main()
