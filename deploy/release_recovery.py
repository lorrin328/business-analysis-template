"""Capture releases, restore only a frozen maintenance point, accept after review.

The CLI checks that systemd is stopped before restoration. Once the candidate has
been started, an operator must independently establish that no new writes occurred
and explicitly pass --confirm-no-new-writes; automatic recovery never assumes this.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from backup_database import backup_database, write_metadata
from backup_policy import DEFAULT_RESERVE, prune_backups, verify_backup

RELEASE_NAME = re.compile(r"release-\d{8}_\d{6}-\d+$")
EXCLUDED_ROOTS = {".git", ".venv", ".tmp", ".uv-cache", ".uv-python", "excel", "data",
                  "output", "outputs", "exports", "backups", "bak", "_external_materials", "node_modules"}


def excluded(relative: Path) -> bool:
    parts = relative.parts
    return (bool(parts) and parts[0] in EXCLUDED_ROOTS
            or any(part in {"__pycache__", ".pytest_cache", "node_modules"} for part in parts)
            or (len(parts) >= 2 and parts[0] == "backend" and
                (parts[1].startswith("venv") or parts[1] in {".venv", "logs", "market_analysis_data"}))
            or any(fnmatch.fnmatch(relative.name, pattern) for pattern in
                   ("*.db", "*.db-*", "*.sqlite*", "*.xlsx", "*.xls", "*.csv", "*.pyc", "*.sync-conflict-*")))


def _write_manifest(root: Path, payload: dict) -> None:
    temp = root / "release.json.tmp"
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.chmod(0o600)
    os.replace(temp, root / "release.json")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_release_artifacts(root: Path, payload: dict) -> None:
    if not payload.get("artifacts"):
        raise ValueError("release artifact checksums are missing")
    for relative, expected in payload["artifacts"].items():
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root) or _hash_file(path) != expected:
            raise ValueError("release artifact checksum verification failed")


def _load(root: str | Path) -> tuple[Path, dict]:
    raw = Path(root)
    if raw.is_symlink():
        raise ValueError("release directory must not be a symlink")
    root = raw.resolve()
    if not RELEASE_NAME.fullmatch(root.name):
        raise ValueError("invalid managed release directory")
    payload = json.loads((root / "release.json").read_text(encoding="utf-8"))
    if Path(payload["release_dir"]).resolve() != root:
        raise ValueError("release manifest directory mismatch")
    app = Path(payload["app_dir"]).resolve()
    if root == app or root.is_relative_to(app) or app.is_relative_to(root):
        raise ValueError("application and recovery directories must be separate")
    return root, payload


def _copy_code(source: Path, destination: Path, relative: Path = Path(), *, remove_extra=False) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise ValueError("code destination must not be a symlink")
    source_names = {path.name for path in source.iterdir()}
    if remove_extra:
        for existing in destination.iterdir():
            if existing.name not in source_names and not excluded(relative / existing.name):
                if existing.is_dir() and not existing.is_symlink():
                    shutil.rmtree(existing)
                else:
                    existing.unlink()
    for item in source.iterdir():
        rel = relative / item.name
        if excluded(rel):
            continue
        target = destination / item.name
        if item.is_symlink() or target.is_symlink():
            raise ValueError("unexpected symlink in managed application code")
        if item.is_dir():
            _copy_code(item, target, rel, remove_extra=remove_extra)
        else:
            shutil.copy2(item, target)


def capture_release(app_dir: str | Path, release_dir: str | Path, database: str | Path,
                    service: str, configs: list[str] | None = None) -> dict:
    app, root = Path(app_dir).resolve(), Path(release_dir).resolve()
    if not RELEASE_NAME.fullmatch(root.name) or root.exists() or root.is_relative_to(app) or app.is_relative_to(root):
        raise ValueError("release snapshot requires a new separate managed directory")
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", service):
        raise ValueError("invalid systemd service name")
    root.mkdir(mode=0o700, parents=True)
    root.chmod(0o700)
    _copy_code(app, root / "code")
    # Recovery must remain runnable after the temporary deployment source is removed
    # or the application itself has been restored to a version without these tools.
    toolkit = root / "recovery-tools"
    toolkit.mkdir()
    for source in (Path(__file__), Path(sys.modules["backup_policy"].__file__),
                   Path(sys.modules["backup_database"].__file__)):
        shutil.copy2(source, toolkit / source.name)
    configuration = []
    for index, name in enumerate(configs or []):
        path = Path(name).absolute()
        record = {"path": str(path), "exists": path.exists() or path.is_symlink()}
        if path.is_symlink():
            record["symlink"] = os.readlink(path)
        elif path.is_file():
            saved = root / f"config-{index}"
            shutil.copy2(path, saved)
            record["saved"] = saved.name
        elif path.exists():
            raise ValueError("only file and symlink configuration entries are supported")
        configuration.append(record)
    payload = {"release_dir": str(root), "app_dir": str(app), "database": str(Path(database).resolve()),
               "service": service, "configs": configuration, "state": "captured", "previous_venv": None,
               "frozen_backup": None, "database_existed": Path(database).is_file()}
    payload["import_lock"] = os.getenv("BUSINESS_ANALYSIS_LOCK") or str(Path(database).resolve().with_suffix(".import.lock"))
    if payload["database_existed"]:
        database_stat = Path(database).stat()
        payload["database_permissions"] = {"mode": database_stat.st_mode & 0o777,
                                            "uid": database_stat.st_uid, "gid": database_stat.st_gid}
    payload["artifacts"] = {path.relative_to(root).as_posix(): _hash_file(path)
                            for path in root.rglob("*") if path.is_file()}
    _write_manifest(root, payload)
    return payload


def update_release(root: str | Path, **values) -> dict:
    directory, payload = _load(root)
    payload.update(values)
    _write_manifest(directory, payload)
    return payload


def freeze_database(root: str | Path, destination: str | Path) -> dict:
    directory, payload = _load(root)
    destination = Path(destination).resolve()
    if destination.parent != directory.parent:
        raise ValueError("frozen backup must be inside the managed backup directory")
    if payload["database_existed"]:
        metadata = backup_database(payload["database"], destination)
        write_metadata(Path(str(destination) + ".meta"), metadata)
        payload["frozen_backup"] = str(destination)
    payload["state"] = "frozen"
    _write_manifest(directory, payload)
    return payload


def restore_release(root: str | Path, *, confirm_no_new_writes: bool = False) -> dict:
    directory, payload = _load(root)
    if payload["state"] in {"started", "healthy", "accepted", "blocked"} and not confirm_no_new_writes:
        raise RuntimeError("candidate was started: automatic code/database rollback refused; stop service, inspect new writes and migration compatibility, then explicitly authorize recovery")
    if payload["state"] not in {"frozen", "mutating", "started", "healthy", "accepted", "blocked"}:
        raise RuntimeError("release has no frozen recovery point")
    verify_release_artifacts(directory, payload)
    frozen = payload.get("frozen_backup")
    if payload["database_existed"]:
        if not frozen:
            raise RuntimeError("missing frozen database backup")
        verify_backup(frozen)
    app, database = Path(payload["app_dir"]), Path(payload["database"])
    if not payload["database_existed"] and database.exists():
        raise RuntimeError("fresh-install database retained; no previous database exists")
    if database.is_symlink():
        raise ValueError("database must not be a symlink")
    previous = Path(payload["previous_venv"]) if payload.get("previous_venv") else None
    if previous and (previous.parent.resolve() != (app / "backend").resolve()
                     or not re.fullmatch(r"venv\.previous\.\d{8}_\d{6}-\d+", previous.name)
                     or previous.is_symlink()):
        raise ValueError("invalid preserved dependency environment")
    # Validate everything before the first mutation. A candidate copy prevents partial DB writes.
    candidate = database.with_name(database.name + ".restore-candidate")
    if candidate.exists():
        raise FileExistsError("a previous recovery candidate requires inspection")
    if frozen:
        if shutil.disk_usage(database.parent).free < Path(frozen).stat().st_size + DEFAULT_RESERVE:
            raise RuntimeError("insufficient space for atomic recovery candidate; current database preserved")
        backup_database(frozen, candidate)
    _copy_code(directory / "code", app, remove_extra=True)
    if previous and previous.is_dir():
        active = app / "backend" / "venv"
        failed = app / "backend" / ("venv.failed." + directory.name.removeprefix("release-"))
        if failed.exists():
            raise FileExistsError("failed dependency directory already exists")
        if active.exists():
            active.rename(failed)
        previous.rename(active)
        if failed.exists():
            shutil.rmtree(failed)
    for record in payload["configs"]:
        path = Path(record["path"])
        if path.is_symlink() or path.is_file():
            path.unlink()
        if record["exists"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            if "symlink" in record:
                path.symlink_to(record["symlink"])
            else:
                shutil.copy2(directory / record["saved"], path)
    if frozen:
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(database) + suffix)
            if sidecar.exists() or sidecar.is_symlink():
                sidecar.unlink()
        os.replace(candidate, database)
        permissions = payload.get("database_permissions", {})
        database.chmod(permissions.get("mode", 0o640))
        if os.name == "posix":
            os.chown(database, permissions.get("uid", os.getuid()), permissions.get("gid", os.getgid()))
    payload["state"] = "restored"
    _write_manifest(directory, payload)
    return payload


def accept_release(root: str | Path) -> dict:
    directory, payload = _load(root)
    if payload["state"] not in {"healthy", "accepted"}:
        raise RuntimeError("only a healthy reviewed release may be accepted")
    frozen = payload.get("frozen_backup")
    if not frozen:
        raise RuntimeError("no verified recovery backup; retention cleanup refused")
    verify_release_artifacts(directory, payload)
    if any(path.is_dir() and RELEASE_NAME.fullmatch(path.name) and path.name > directory.name
           for path in directory.parent.iterdir()):
        raise RuntimeError("a newer release exists; stale acceptance refused")
    verify_backup(frozen)
    removed = prune_backups(directory.parent, frozen)
    # Keep the current rollback package and its dependency environment. Other packages
    # are not deleted unless their complete accepted manifest proves ownership.
    for older in directory.parent.iterdir():
        if older == directory or older.is_symlink() or not older.is_dir() or not RELEASE_NAME.fullmatch(older.name):
            continue
        try:
            _, old = _load(older)
        except (OSError, ValueError, KeyError):
            continue
        if old.get("state") != "accepted" or old.get("app_dir") != payload["app_dir"]:
            continue
        previous = Path(old["previous_venv"]) if old.get("previous_venv") else None
        if previous and previous.exists() and str(previous) != payload.get("previous_venv"):
            if previous.parent.resolve() != (Path(payload["app_dir"]) / "backend").resolve() or previous.is_symlink() or not re.fullmatch(r"venv\.previous\.\d{8}_\d{6}-\d+", previous.name):
                raise ValueError("unsafe old dependency path; cleanup refused")
            shutil.rmtree(previous)
        shutil.rmtree(older)
    payload["state"] = "accepted"
    _write_manifest(directory, payload)
    return {"state": "accepted", "retainedBackup": frozen, "retainedRelease": str(directory), "removedBackups": removed}


@contextmanager
def release_lock(directory: Path):
    """Use the shell's inherited lock, or acquire it for standalone recovery/acceptance."""
    with file_lock(directory.parent / ".deployment.lock", "BUSINESS_ANALYSIS_DEPLOY_LOCK_FD"):
        yield


@contextmanager
def file_lock(lock_path: Path, inherited_variable: str):
    import fcntl
    inherited = os.getenv(inherited_variable)
    if inherited:
        descriptor = int(inherited)
        actual, expected = os.fstat(descriptor), lock_path.stat()
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise RuntimeError("inherited lock does not match its expected file")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    else:
        with lock_path.open("a") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture")
    capture.add_argument("--app-dir", required=True)
    capture.add_argument("--release-dir", required=True)
    capture.add_argument("--database", required=True)
    capture.add_argument("--service", required=True)
    capture.add_argument("--config", action="append", default=[])
    for name in ("freeze", "mark", "restore", "accept-release"):
        command = commands.add_parser(name)
        command.add_argument("--release-dir", required=True)
        if name == "freeze":
            command.add_argument("--destination", required=True)
        elif name == "mark":
            command.add_argument("--state", required=True, choices=("mutating", "started", "healthy", "blocked"))
            command.add_argument("--previous-venv")
        elif name == "restore":
            command.add_argument("--confirm-no-new-writes", action="store_true")
        else:
            command.add_argument("--confirm-review-complete", action="store_true", required=True)
    args = parser.parse_args()
    with release_lock(Path(args.release_dir).resolve()):
        _execute(args)


def _execute(args) -> None:
    if args.command == "capture":
        capture_release(args.app_dir, args.release_dir, args.database, args.service, args.config)
    elif args.command == "freeze":
        _require_stopped_service(args.release_dir)
        _, data = _load(args.release_dir)
        with file_lock(Path(data["import_lock"]), "BUSINESS_ANALYSIS_IMPORT_LOCK_FD"):
            freeze_database(args.release_dir, args.destination)
    elif args.command == "mark":
        values = {"state": args.state}
        if args.previous_venv:
            values["previous_venv"] = args.previous_venv
        update_release(args.release_dir, **values)
    elif args.command == "restore":
        _require_stopped_service(args.release_dir)
        _, data = _load(args.release_dir)
        with file_lock(Path(data["import_lock"]), "BUSINESS_ANALYSIS_IMPORT_LOCK_FD"):
            restore_release(args.release_dir, confirm_no_new_writes=args.confirm_no_new_writes)
        print(json.dumps({"state": "restored", "serviceRemainsStopped": True,
                          "nextCommands": ["systemctl daemon-reload", "nginx -t",
                                           f"systemctl start {data['service']}"]}))
    else:
        print(json.dumps(accept_release(args.release_dir)))


def _require_stopped_service(root: str | Path) -> None:
    _, data = _load(root)
    probe = subprocess.run(["systemctl", "is-active", "--quiet", data["service"]], check=False)
    if probe.returncode not in {3, 4}:  # inactive/failed, or a not-yet-created unit
        raise RuntimeError("service must be confirmed inactive before frozen backup or recovery")


if __name__ == "__main__":
    main()
