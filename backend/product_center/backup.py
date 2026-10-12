"""Consistent local recovery sets for SQLite plus immutable research originals."""
from __future__ import annotations

import hashlib
from contextlib import closing
import io
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import tempfile
import zipfile


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _package_manifest_hash(raw):
    """Bind a stored package to the database's canonical manifest identity."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if archive.namelist().count('manifest.json') != 1:
                raise ValueError('导入包清单缺失或重复')
            if archive.getinfo('manifest.json').file_size > 16 * 1024 * 1024:
                raise ValueError('导入包清单超过16MB')
            manifest = json.loads(archive.read('manifest.json').decode('utf-8-sig'))
            if not isinstance(manifest, dict):
                raise ValueError('导入包清单格式无效')
            canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':'), allow_nan=False).encode('utf-8')
            return _hash(canonical)
    except (zipfile.BadZipFile, KeyError, UnicodeError, TypeError, RuntimeError,
            NotImplementedError, RecursionError) as exc:
        raise ValueError('导入包清单无法校验') from exc


def _entry_allowed(name):
    return name == 'business_data.db' or bool(re.fullmatch(
        r'product_center_data/(?:files/[0-9a-f]{64}\.(?:pdf|png|jpe?g|docx|xlsx|pptx)|packages/[0-9a-f]{64}\.zip)', name))


def create_backup(database: Path, data_root: Path, output: Path):
    """Caller must hold the same import lock as the running application."""
    database, data_root, output = database.resolve(strict=True), data_root.resolve(strict=True), output.resolve()
    if output.exists():
        raise ValueError('备份目标已存在，拒绝覆盖')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='pc-backup-', dir=output.parent) as temp:
        snapshot = Path(temp) / 'business_data.db'
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)) as source, closing(sqlite3.connect(snapshot)) as dest:
            source.backup(dest)
            if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or dest.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('数据库完整性校验失败')
            tables = {r[0] for r in dest.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            paths = []
            active = None
            if 'product_center_sources' in tables:
                for entry, sha in dest.execute('SELECT DISTINCT entry,sha256 FROM product_center_sources'):
                    paths.append((entry, sha))
                for (sha,) in dest.execute('SELECT manifest_hash FROM product_center_batches'):
                    paths.append((f'packages/{sha}.zip', None))
                row = dest.execute('''SELECT p.batch_id FROM product_center_state s
                    JOIN product_center_publications p ON p.id=s.publication_id WHERE s.id=1''').fetchone()
                active = row[0] if row else None
        items = {'business_data.db': snapshot.read_bytes()}
        for entry, sha in paths:
            target = data_root / entry
            if not _entry_allowed('product_center_data/'+entry) or target.is_symlink() or not target.resolve().is_relative_to(data_root):
                raise ValueError('资料备份路径无效')
            raw = target.read_bytes()
            if sha and _hash(raw) != sha:
                raise ValueError('资料备份前哈希校验失败')
            if entry.startswith('packages/') and _package_manifest_hash(raw) != PurePosixPath(entry).stem:
                raise ValueError('导入包清单哈希与数据库不符')
            items['product_center_data/'+entry] = raw
        meta = {'formatVersion':1,'activeBatchId':active, 'integrityCheck':'ok',
                'files':{name:{'sha256':_hash(raw),'bytes':len(raw)} for name,raw in items.items()}}
        # Exclusive target prevents accidental overwrite of an existing recovery point.
        with output.open('xb') as stream, zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,raw in items.items():
                archive.writestr(name,raw)
            archive.writestr('backup-manifest.json',json.dumps(meta,ensure_ascii=False,sort_keys=True))
        output.chmod(0o600)
    return verify_backup(output)


def verify_backup(archive_path: Path):
    with zipfile.ZipFile(archive_path) as archive:
        infos=archive.infolist()
        names=[i.filename for i in infos]
        if len(set(names))!=len(names) or len(names)>20000 or sum(i.file_size for i in infos)>8*1024**3:
            raise ValueError('备份文件数量或大小无效')
        for info in infos:
            if (info.filename != 'backup-manifest.json' and not _entry_allowed(info.filename)) or stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1:
                raise ValueError('备份包含非法文件')
        meta=json.loads(archive.read('backup-manifest.json'))
        if meta.get('formatVersion')!=1 or set(names)!=set(meta['files'])|{'backup-manifest.json'} or 'business_data.db' not in meta['files']:
            raise ValueError('备份清单不完整')
        for name,expected in meta['files'].items():
            raw=archive.read(name)
            if _hash(raw)!=expected['sha256'] or len(raw)!=expected['bytes']:
                raise ValueError('备份哈希或长度校验失败')
        with tempfile.TemporaryDirectory(prefix='pc-verify-') as temp:
            db=Path(temp)/'snapshot.db'
            db.write_bytes(archive.read('business_data.db'))
            with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as conn:
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or conn.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('备份数据库完整性校验失败')
                tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'product_center_sources' in tables:
                    for entry,sha in conn.execute('SELECT DISTINCT entry,sha256 FROM product_center_sources'):
                        name='product_center_data/'+entry
                        if name not in meta['files'] or meta['files'][name]['sha256']!=sha:
                            raise ValueError('备份缺少数据库引用的资料')
                    for (sha,) in conn.execute('SELECT manifest_hash FROM product_center_batches'):
                        name = 'product_center_data/packages/'+sha+'.zip'
                        if name not in meta['files']:
                            raise ValueError('备份缺少导入包')
                        if _package_manifest_hash(archive.read(name)) != sha:
                            raise ValueError('备份导入包清单哈希与数据库不符')
        return {'formatVersion':1,'activeBatchId':meta.get('activeBatchId'),'fileCount':len(meta['files']),
                'integrityCheck':'ok','sha256':_hash(Path(archive_path).read_bytes())}


def restore_backup(archive_path: Path, destination: Path):
    result=verify_backup(archive_path)
    destination=destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('恢复仅允许写入空目录，拒绝覆盖现有数据')
    destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    with zipfile.ZipFile(archive_path) as archive:
        for name in archive.namelist():
            if name=='backup-manifest.json':
                continue
            target=destination/PurePosixPath(name)
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if not target.resolve().is_relative_to(destination) or target.is_symlink():
                raise ValueError('恢复目标路径无效')
            with target.open('xb') as stream:
                stream.write(archive.read(name))
            target.chmod(0o600)
    return result
