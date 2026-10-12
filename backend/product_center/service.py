"""Immutable reviewed packages, transactional publication and source-bound queries."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid
import zipfile

from fastapi import HTTPException
from db.connection import get_db
from services.operation_lock import operation_lock

DIMENSIONS = ('客户需求', '保障责任', '利益水平', '退出与灵活性', '服务权益', '渠道承接', '公司经济性')
MAX_PACKAGE_BYTES = 100 * 1024 * 1024
MAX_EXPANDED_BYTES = 300 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MEDIA = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg',
         '.jpeg': 'image/jpeg', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
         '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'}
VERSION_FIELDS = ('id', 'name', 'code', 'channel', 'stage', 'insurer', 'revision', 'identityStatus',
                  'saleStatus', 'responsibilityType', 'benefitMechanism', 'reviewDate', 'limitations', 'sourceIds')
FACT_FIELDS = ('id', 'versionId', 'dimension', 'label', 'text', 'status', 'sourceIds', 'locator', 'reviewDate', 'limitations')
SCENARIO_FIELDS = ('id', 'versionId', 'productName', 'channel', 'partition', 'benefitNature', 'age', 'sex',
                   'payYears', 'payLabel', 'annualPremium', 'totalPremium', 'paidPremiumAtExit', 'horizonYear',
                   'irr', 'originalIrr', 'computedIrr', 'arithmeticStatus', 'contractStatus', 'terminalValue',
                   'incomeTotal', 'variant', 'status', 'limitations', 'sourceIds', 'scenarioLabel', 'sourceEvidence')
SOURCE_FIELDS = ('id', 'filename', 'sha256', 'mediaType', 'reviewDate', 'versionIds', 'locator')


def _bad(message):
    raise HTTPException(400, message)


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _no_local_paths(value, depth=0):
    """Reject private filesystem locations even in free-form reviewer metadata."""
    if depth > 64:
        _bad('清单嵌套层数超限')
    if isinstance(value, str):
        if re.search(r'(?i)(?:[a-z]:[\\/]|\\\\[^\\\s]+\\|/(?:home|Users|var|opt|tmp|mnt|data)/)', value):
            _bad('清单不得包含本地绝对路径；请使用来源编号与页码')
    elif isinstance(value, dict):
        for key, item in value.items():
            _no_local_paths(key, depth + 1)
            _no_local_paths(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _no_local_paths(item, depth + 1)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _bad('清单包含重复字段')
        result[key] = value
    return result


def storage_root() -> Path:
    # Resolve at call time so tests and explicit database locations remain isolated.
    from db import connection
    root = Path(os.environ.get('PRODUCT_CENTER_DATA_DIR') or (Path(connection.DB_PATH).resolve().parent / 'product_center_data'))
    if root.is_symlink():
        _bad('资料存储目录不能是符号链接')
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('packages', 'files'):
        if (root / name).is_symlink():
            _bad('资料存储目录不能是符号链接')
        (root / name).mkdir(exist_ok=True, mode=0o700)
    return root


def _text(value, label, *, optional=False, limit=20000):
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > limit or '\x00' in value:
        _bad(f'{label} 格式无效')


def _number(value, label, *, optional=True):
    if optional and value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _bad(f'{label} 必须为有限数值或空值')


def _refs(row, key, allowed):
    refs = row.get(key, [])
    if not isinstance(refs, list) or any(not isinstance(x, str) or x not in allowed for x in refs) or len(refs) != len(set(refs)):
        _bad(f'{key} 引用了不存在或重复的记录')


def _rows(manifest, key, limit=20000):
    rows = manifest.get(key)
    if not isinstance(rows, list) or len(rows) > limit or any(not isinstance(x, dict) for x in rows):
        _bad(f'{key} 必须为受限长度的记录数组')
    ids = []
    for row in rows:
        _text(row.get('id'), f'{key}.id', limit=160)
        if not re.fullmatch(r'[A-Za-z0-9_.:-]+', row['id']):
            _bad(f'{key}.id 包含非法字符')
        ids.append(row['id'])
        for field in ('limitations',):
            if field in row and (not isinstance(row[field], list) or any(not isinstance(s, str) for s in row[field])):
                _bad(f'{key}.{field} 必须为文字数组')
    if len(set(ids)) != len(ids):
        _bad(f'{key} 存在重复 ID')
    return rows


def validate_package(data: bytes):
    """Validate every entry before writing anything; never extract caller paths."""
    if len(data) > MAX_PACKAGE_BYTES:
        raise HTTPException(413, '导入包超过100MB')
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError):
        _bad('导入包必须为有效ZIP')
    with z:
        infos = z.infolist()
        if not infos or len(infos) > 501 or sum(i.file_size for i in infos) > MAX_EXPANDED_BYTES:
            _bad('导入包展开大小或文件数量超限')
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or 'manifest.json' not in names:
            _bad('导入包缺少清单或存在重复文件')
        for i in infos:
            p = PurePosixPath(i.filename)
            mode = i.external_attr >> 16
            if (i.flag_bits & 1 or i.is_dir() or i.file_size > MAX_FILE_BYTES
                    or '\\' in i.filename or ':' in i.filename or p.is_absolute()
                    or any(part in ('.', '..') for part in p.parts)
                    or p.as_posix() != i.filename or stat.S_ISLNK(mode)
                    or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))):
                _bad('导入包含非法路径、链接或超限文件')
        if z.getinfo('manifest.json').file_size > 16 * 1024 * 1024:
            _bad('清单超过16MB')
        try:
            manifest = json.loads(z.read('manifest.json').decode('utf-8-sig'),
                                  parse_constant=lambda x: _bad('清单含非法数值'), object_pairs_hook=_unique_object)
        except (ValueError, UnicodeError, zipfile.BadZipFile, RecursionError):
            _bad('导入清单不是有效JSON')
        if not isinstance(manifest, dict) or manifest.get('formatVersion') != 1:
            _bad('不支持的导入格式')
        _no_local_paths(manifest)
        _text(manifest.get('sourceDate'), 'sourceDate', limit=10)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', manifest['sourceDate']):
            _bad('资料日期无效')
        _text(manifest.get('converterVersion'), 'converterVersion', limit=60)
        versions = _rows(manifest, 'versions', 1000)
        facts = _rows(manifest, 'facts')
        scenarios = _rows(manifest, 'scenarios', 10000)
        sources = _rows(manifest, 'sources', 500)
        version_ids = {r['id'] for r in versions}
        source_ids = {r['id'] for r in sources}
        version_map = {r['id']: r for r in versions}
        file_map = {}
        for row in sources:
            sha = row.get('sha256', '')
            entry = row.get('entry', '')
            _text(sha, '资料哈希', limit=64)
            _text(entry, '资料定位', limit=120)
            suffix = PurePosixPath(entry).suffix.lower()
            if not re.fullmatch(r'[0-9a-f]{64}', sha) or suffix not in MEDIA or entry != f'files/{sha}{suffix}':
                _bad('资料定位必须为内容哈希文件名')
            filename = row.get('filename', '')
            _text(filename, '资料名称', limit=240)
            if any(x in filename for x in ('/', '\\', ':', '\r', '\n')):
                _bad('资料名称不得包含目录或控制字符')
            if row.get('mediaType') != MEDIA[suffix] or entry not in names:
                _bad('资料类型或文件缺失')
            _refs(row, 'versionIds', version_ids)
            try:
                raw = z.read(entry)
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
                _bad('资料无法解压或校验失败')
            if hashlib.sha256(raw).hexdigest() != sha:
                _bad('资料哈希校验失败')
            signatures = {'.pdf': b'%PDF-', '.png': b'\x89PNG\r\n\x1a\n', '.jpg': b'\xff\xd8', '.jpeg': b'\xff\xd8', '.docx': b'PK', '.xlsx': b'PK', '.pptx': b'PK'}
            if not raw.startswith(signatures[suffix]):
                _bad('资料内容与声明类型不一致')
            file_map[entry] = raw
        if set(names) != {'manifest.json', *file_map}:
            _bad('导入包含未登记文件')
        for row in versions:
            for key in ('name', 'insurer', 'revision'):
                _text(row.get(key), f'产品.{key}', limit=500)
            for key in ('code', 'responsibilityType', 'benefitMechanism', 'reviewDate'):
                _text(row.get(key), f'产品.{key}', optional=True, limit=500)
            if row.get('identityStatus') == 'confirmed' and not row.get('code'):
                _bad('缺少产品代码时身份必须保留待核')
            if (row.get('channel') not in ('OTO', '证保') or row.get('stage') not in ('formal', 'development')
                    or row.get('identityStatus') not in ('confirmed', 'provisional') or row.get('saleStatus') != 'unknown'):
                _bad('产品渠道、阶段或证据状态无效；首期不导入在售认定')
            _refs(row, 'sourceIds', source_ids)
            if not row.get('sourceIds'):
                _bad('产品必须有来源')
        for row in facts:
            if not isinstance(row.get('versionId'), str) or row['versionId'] not in version_ids or row.get('dimension') not in DIMENSIONS:
                _bad('责任事实引用无效')
            if row.get('status') not in ('已确认', '开发稿载', '假设下复算', '待核'):
                _bad('事实核验状态无效')
            for key in ('label', 'text'):
                _text(row.get(key), f'事实.{key}')
            for key in ('locator', 'reviewDate'):
                _text(row.get(key), f'事实.{key}', optional=True)
            _refs(row, 'sourceIds', source_ids)
            if row['status'] != '待核' and not row.get('sourceIds'):
                _bad('非待核事实必须有来源')
        for row in scenarios:
            vid = row.get('versionId')
            if vid is not None and (not isinstance(vid, str) or vid not in version_ids or row.get('channel') != version_map[vid]['channel']):
                _bad('利益方案跨产品或渠道引用无效')
            if row.get('partition') not in ('guarantee', 'example', 'development') or row.get('benefitNature') not in ('guaranteed', 'illustrated', 'assumed', 'development'):
                _bad('利益方案分区或利益性质无效')
            if vid and version_map[vid]['stage'] == 'development' and row['partition'] != 'development':
                _bad('开发稿利益不得进入正式产品比较')
            if row['partition'] == 'guarantee' and row['benefitNature'] != 'guaranteed':
                _bad('保证比较不得混入演示或假设')
            for key in ('age', 'payYears', 'annualPremium', 'totalPremium', 'paidPremiumAtExit', 'horizonYear', 'irr', 'originalIrr', 'computedIrr', 'terminalValue', 'incomeTotal'):
                _number(row.get(key), f'方案.{key}')
            for key in ('productName', 'channel', 'sex', 'payLabel', 'variant', 'status', 'arithmeticStatus', 'contractStatus', 'scenarioLabel'):
                if row.get(key) not in (None, ''):
                    _text(row.get(key), f'方案.{key}', limit=500)
            _refs(row, 'sourceIds', source_ids)
            flows = row.get('cashflows')
            if not isinstance(flows, list) or len(flows) > 2000:
                _bad('现金流必须为受限长度的数组')
            for flow in flows:
                if not isinstance(flow, dict):
                    _bad('现金流格式无效')
                _number(flow.get('timeYear'), '现金流时点', optional=False)
                _number(flow.get('amount'), '现金流金额', optional=False)
                if flow['timeYear'] < 0 or flow['timeYear'] > 200:
                    _bad('现金流时点超限')
                _text(flow.get('kind'), '现金流性质', limit=240)
            # The uploaded cached result is never treated as a verified calculation.
            if row.get('irr') is not None:
                if not flows or not row.get('sourceIds'):
                    _bad('收益结果必须具有现金流和来源')
                from product_center.irr import solve_irr
                try:
                    calculated = solve_irr(flows)
                    if isinstance(calculated, dict):
                        calculated = calculated.get('irr')
                    if isinstance(calculated, tuple):
                        calculated = calculated[0]
                    if abs(calculated - row['irr']) > 1e-8:
                        _bad('收益结果与现金流复算不符')
                except HTTPException:
                    raise
                except (ValueError, ArithmeticError, TypeError, OverflowError):
                    _bad('现金流无法得到唯一有效IRR')
            pending = ('待核' in str(row.get('status', '')) + str(row.get('contractStatus', ''))
                       or row.get('contractStatus') == 'timing_pending')
            if pending and row.get('irr') is not None:
                _bad('合同边界待核结果必须为空')
        if not isinstance(manifest.get('gaps', []), list) or not isinstance(manifest.get('report', {}), dict):
            _bad('缺口与校验报告格式无效')
        return manifest, file_map


def _active(conn):
    return conn.execute('''SELECT p.id publication_id, p.batch_id FROM product_center_state s
        JOIN product_center_publications p ON p.id=s.publication_id WHERE s.id=1''').fetchone()


def active_batch_id(conn):
    row = _active(conn)
    return row['batch_id'] if row else None


def _public(row, fields):
    return {k: row.get(k) for k in fields}


def _counts(manifest):
    scenarios = manifest['scenarios']
    return {'versions': len(manifest['versions']), 'facts': len(manifest['facts']),
            'scenarios': len(scenarios), 'sources': len(manifest['sources']),
            'pendingIrr': sum(x.get('irr') is None for x in scenarios),
            'quarantinedScenarios': sum(x.get('versionId') is None for x in scenarios),
            'guarantee': sum(x.get('partition') == 'guarantee' for x in scenarios)}


def _audit(conn, action, user, batch_id, **detail):
    from services.audit_log import actor_from_user
    user_id, username = actor_from_user(user)
    conn.execute('''INSERT INTO operation_logs(user_id,username,action,status,detail)
        VALUES (?,?,?,'success',?)''', (user_id, username, f'product_center_{action}', _dump({'batchId':batch_id, **detail})))


def preview_package(data: bytes, user: dict):
    manifest, files = validate_package(data)
    digest = hashlib.sha256(_dump(manifest).encode('utf-8')).hexdigest()
    with operation_lock('product-center-preview', timeout=1):
        with get_db() as conn:
            previous = conn.execute('SELECT id FROM product_center_batches WHERE manifest_hash=?', (digest,)).fetchone()
            if previous:
                result = import_detail(previous['id'], conn=conn)
                _audit(conn, 'preview', user, previous['id'], duplicate=True)
                conn.commit()
                result['duplicate'] = True
                return result
            root = storage_root()
            for entry, raw in files.items():
                target = root / entry
                if target.is_symlink():
                    _bad('资料存储位置无效')
                if target.exists():
                    if hashlib.sha256(target.read_bytes()).hexdigest() != PurePosixPath(entry).stem:
                        _bad('现有资料完整性校验失败')
                else:
                    with target.open('xb') as stream:
                        stream.write(raw)
                    target.chmod(0o600)
            archive = root / 'packages' / f'{digest}.zip'
            if not archive.exists():
                with archive.open('xb') as stream:
                    stream.write(data)
                archive.chmod(0o600)
            batch_id = uuid.uuid4().hex
            current = active_batch_id(conn)
            old = {r['id'] for r in conn.execute('SELECT id FROM product_center_versions WHERE batch_id=?', (current,))}
            new = {r['id'] for r in manifest['versions']}
            diff = {'addedVersions': len(new-old), 'removedVersions': len(old-new), 'retainedVersions': len(new & old), 'previousBatchId': current}
            report = dict(manifest.get('report', {}))
            report['counts'] = _counts(manifest)
            conn.execute('''INSERT INTO product_center_batches(id,manifest_hash,source_date,converter_version,
                report_json,gaps_json,diff_json,created_by) VALUES (?,?,?,?,?,?,?,?)''',
                (batch_id, digest, manifest['sourceDate'], manifest['converterVersion'], _dump(report), _dump(manifest.get('gaps', [])), _dump(diff), user.get('id')))
            for row in manifest['versions']:
                conn.execute('INSERT INTO product_center_versions VALUES (?,?,?,?,?,?,?)',
                    (batch_id,row['id'],row['channel'],row['stage'],row['name'],row.get('code'),_dump(_public(row,VERSION_FIELDS))))
            for row in manifest['sources']:
                conn.execute('INSERT INTO product_center_sources VALUES (?,?,?,?,?)',
                    (batch_id,row['id'],row['sha256'],row['entry'],_dump(_public(row,SOURCE_FIELDS))))
            for row in manifest['facts']:
                conn.execute('INSERT INTO product_center_facts VALUES (?,?,?,?,?)',
                    (batch_id,row['id'],row['versionId'],row['dimension'],_dump(_public(row,FACT_FIELDS))))
            for row in manifest['scenarios']:
                conn.execute('INSERT INTO product_center_scenarios VALUES (?,?,?,?,?)',
                    (batch_id,row['id'],row.get('versionId'),row['partition'],_dump(_public(row,SCENARIO_FIELDS))))
                conn.executemany('INSERT INTO product_center_cashflows VALUES (?,?,?,?,?,?)',
                    [(batch_id,row['id'],i,x['timeYear'],x['amount'],x['kind']) for i,x in enumerate(row['cashflows'])])
            for kind, collection in [('version','versions'), ('fact','facts'), ('scenario','scenarios')]:
                conn.executemany('INSERT INTO product_center_evidence VALUES (?,?,?,?)',
                    [(batch_id,kind,row['id'],sid) for row in manifest[collection] for sid in row.get('sourceIds',[])])
            _audit(conn, 'preview', user, batch_id, duplicate=False, counts=_counts(manifest))
            conn.commit()
            result = import_detail(batch_id, conn=conn)
            result['duplicate'] = False
            return result


def import_detail(batch_id, *, conn=None):
    if conn is None:
        with get_db() as connection:
            return import_detail(batch_id, conn=connection)
    row = conn.execute('SELECT * FROM product_center_batches WHERE id=?',(batch_id,)).fetchone()
    if not row:
        raise HTTPException(404, '导入批次不存在')
    active = active_batch_id(conn)
    published = conn.execute('SELECT 1 FROM product_center_publications WHERE batch_id=?',(batch_id,)).fetchone()
    batch = {'id':row['id'],'sourceDate':row['source_date'],'converterVersion':row['converter_version'],
             'createdAt':row['created_at'],'status':'published' if active==batch_id else ('archived' if published else 'preview')}
    diff = json.loads(row['diff_json'])
    if active != batch_id:
        diff = {'previousBatchId':active}
        for kind in ('versions', 'facts', 'scenarios', 'sources'):
            old = {r['id']:r['data_json'] for r in conn.execute(f'SELECT id,data_json FROM product_center_{kind} WHERE batch_id=?', (active,))}
            new = {r['id']:r['data_json'] for r in conn.execute(f'SELECT id,data_json FROM product_center_{kind} WHERE batch_id=?', (batch_id,))}
            label = kind[0].upper() + kind[1:]
            diff['added'+label] = len(new.keys()-old.keys())
            diff['removed'+label] = len(old.keys()-new.keys())
            diff['retained'+label] = len(new.keys() & old.keys())
            diff['changed'+label] = sum(new[k] != old[k] for k in new.keys() & old.keys())
    return {'batch':batch,'report':json.loads(row['report_json']),'gaps':json.loads(row['gaps_json']), 'diff':diff}


def list_imports():
    with get_db() as conn:
        rows = conn.execute('SELECT id FROM product_center_batches ORDER BY created_at DESC,rowid DESC LIMIT 100').fetchall()
        return {'items':[import_detail(r['id'],conn=conn)['batch'] for r in rows], 'activeBatchId':active_batch_id(conn)}


def _verified_batch(conn, batch_id):
    row = conn.execute('SELECT manifest_hash FROM product_center_batches WHERE id=?', (batch_id,)).fetchone()
    if not row:
        raise HTTPException(404, '导入批次不存在')
    root = storage_root()
    archive = root / 'packages' / f'{row["manifest_hash"]}.zip'
    if not archive.is_file() or archive.is_symlink():
        _bad('导入包已缺失，不能切换发布')
    manifest, files = validate_package(archive.read_bytes())
    if hashlib.sha256(_dump(manifest).encode('utf-8')).hexdigest() != row['manifest_hash']:
        _bad('预检后导入包发生变化')
    for entry in files:
        file = root / entry
        if file.is_symlink() or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != PurePosixPath(entry).stem:
            _bad('预检后资料发生变化')


def publish(batch_id, user):
    with operation_lock('product-center-publish', timeout=1):
        with get_db() as conn:
            row = conn.execute('SELECT manifest_hash FROM product_center_batches WHERE id=?',(batch_id,)).fetchone()
            if not row:
                raise HTTPException(404,'导入批次不存在')
            current = _active(conn)
            if current and current['batch_id']==batch_id:
                return {'activeBatchId':batch_id,'duplicate':True}
            _verified_batch(conn, batch_id)
            conn.execute('BEGIN IMMEDIATE')
            # Re-read publication inside the write transaction.
            current = _active(conn)
            conn.execute('INSERT INTO product_center_publications(batch_id,previous_id,published_by) VALUES (?,?,?)',
                         (batch_id,current['publication_id'] if current else None,user.get('id')))
            event_id=conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.execute('UPDATE product_center_state SET publication_id=? WHERE id=1',(event_id,))
            _audit(conn, 'publish', user, batch_id)
            conn.commit()
            return {'activeBatchId':batch_id,'duplicate':False}


def withdraw(batch_id, user):
    with operation_lock('product-center-withdraw', timeout=1):
        with get_db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            active=_active(conn)
            if not active or active['batch_id']!=batch_id:
                raise HTTPException(409,'仅可撤回当前发布批次')
            event=conn.execute('SELECT previous_id FROM product_center_publications WHERE id=?',(active['publication_id'],)).fetchone()
            if event['previous_id'] is not None:
                previous = conn.execute('SELECT batch_id FROM product_center_publications WHERE id=?', (event['previous_id'],)).fetchone()
                _verified_batch(conn, previous['batch_id'])
            conn.execute('UPDATE product_center_publications SET withdrawn_at=CURRENT_TIMESTAMP WHERE id=?',(active['publication_id'],))
            conn.execute('UPDATE product_center_state SET publication_id=? WHERE id=1',(event['previous_id'],))
            _audit(conn, 'withdraw', user, batch_id)
            conn.commit()
            return {'activeBatchId':active_batch_id(conn),'withdrawnBatchId':batch_id}


def products(q='', channel=None, stage='formal', responsibility_type=None, benefit_mechanism=None):
    with get_db() as conn:
        batch=active_batch_id(conn)
        all_rows=[json.loads(r[0]) for r in conn.execute('SELECT data_json FROM product_center_versions WHERE batch_id=? ORDER BY channel,name,id',(batch,))]
        rows=[r for r in all_rows if (not q or q.casefold() in (r['name']+' '+str(r.get('code') or '')).casefold())
              and (not channel or r['channel']==channel) and (stage=='all' or r['stage']==stage)
              and (not responsibility_type or r.get('responsibilityType')==responsibility_type)
              and (not benefit_mechanism or r.get('benefitMechanism')==benefit_mechanism)]
        facets={key:sorted({r.get(field) for r in all_rows if r.get(field)}) for key,field in [('channels','channel'),('responsibilityTypes','responsibilityType'),('benefitMechanisms','benefitMechanism')]}
        report=import_detail(batch,conn=conn)['report'] if batch else {}
        return {'items':rows,'total':len(rows),'activeBatchId':batch,'facets':facets,'report':report}


def _version(conn,batch,version_id):
    row=conn.execute('SELECT data_json FROM product_center_versions WHERE batch_id=? AND id=?',(batch,version_id)).fetchone()
    if not row:
        raise HTTPException(404,'当前发布中没有该产品版本')
    return json.loads(row[0])


def _sources(conn, batch, ids):
    return [json.loads(r['data_json']) for r in conn.execute(
        'SELECT id,data_json FROM product_center_sources WHERE batch_id=?', (batch,)) if r['id'] in ids]


def product_detail(version_id):
    with get_db() as conn:
        batch=active_batch_id(conn)
        version=_version(conn,batch,version_id)
        facts=[json.loads(r[0]) for r in conn.execute('SELECT data_json FROM product_center_facts WHERE batch_id=? AND version_id=? ORDER BY rowid',(batch,version_id))]
        ids=set(version.get('sourceIds') or []) | {s for fact in facts for s in fact.get('sourceIds') or []}
        ids.update(r[0] for r in conn.execute('''SELECT e.source_id FROM product_center_evidence e
            JOIN product_center_scenarios s ON s.batch_id=e.batch_id AND s.id=e.entity_id
            WHERE e.batch_id=? AND e.entity_type='scenario' AND s.version_id=?''', (batch,version_id)))
        sources=_sources(conn,batch,ids)
        counts={r['partition_key']:r['n'] for r in conn.execute('SELECT partition_key,COUNT(*) n FROM product_center_scenarios WHERE batch_id=? AND version_id=? GROUP BY partition_key',(batch,version_id))}
        return {'product':version,'facts':facts,'sources':sources,'scenarioCounts':counts}


def _scenarios(conn,batch,version_ids,partition,pay_years=None,horizon_year=None):
    placeholders=','.join('?' for _ in version_ids)
    rows=[json.loads(r[0]) for r in conn.execute(f'SELECT data_json FROM product_center_scenarios WHERE batch_id=? AND version_id IN ({placeholders}) AND partition_key=? ORDER BY rowid',(batch,*version_ids,partition))]
    return [r for r in rows if (pay_years is None or r.get('payYears')==pay_years) and (horizon_year is None or r.get('horizonYear')==horizon_year)]


def scenarios(version_id,partition,pay_years=None,horizon_year=None):
    with get_db() as conn:
        batch=active_batch_id(conn)
        _version(conn,batch,version_id)
        rows=_scenarios(conn,batch,[version_id],partition,pay_years,horizon_year)
        return {'items':rows,'total':len(rows)}


def cashflows(scenario_id):
    with get_db() as conn:
        batch=active_batch_id(conn)
        row=conn.execute('SELECT data_json,version_id FROM product_center_scenarios WHERE batch_id=? AND id=?',(batch,scenario_id)).fetchone()
        if not row or not row['version_id']:
            raise HTTPException(404,'方案不存在或产品身份待核')
        flows=[{'timeYear':r['time_year'],'amount':r['amount'],'kind':r['kind']} for r in conn.execute('SELECT * FROM product_center_cashflows WHERE batch_id=? AND scenario_id=? ORDER BY sequence',(batch,scenario_id))]
        scenario=json.loads(row['data_json'])
        return {'scenario':scenario,'cashflows':flows,'sources':_sources(conn,batch,set(scenario.get('sourceIds') or []))}


def compare(version_ids,partition='guarantee',pay_years=None,horizon_year=None):
    if not isinstance(version_ids,list) or any(not isinstance(v,str) for v in version_ids) or not 2<=len(version_ids)<=4 or len(set(version_ids))!=len(version_ids):
        _bad('请选择2至4个不同产品版本')
    with get_db() as conn:
        batch=active_batch_id(conn)
        versions=[_version(conn,batch,v) for v in version_ids]
        facts=[json.loads(r[0]) for r in conn.execute('SELECT data_json FROM product_center_facts WHERE batch_id=?',(batch,))]
        rows=_scenarios(conn,batch,version_ids,partition,pay_years,horizon_year)
        dimensions=[{'dimension':d,'items':[{'versionId':vid,'facts':[f for f in facts if f['versionId']==vid and f['dimension']==d]} for vid in version_ids]} for d in DIMENSIONS]
        differences=[]
        for field,label in [('channel','渠道'),('stage','材料阶段'),('responsibilityType','保险责任类型'),('benefitMechanism','利益机制')]:
            if len({v.get(field) for v in versions})>1:
                differences.append(f'{label}不同，须分场景理解')
        for field,label in [('age','年龄'),('sex','性别'),('totalPremium','计划总投入'),('payYears','缴费期间'),('horizonYear','退出时点'),('variant','保障或领取方案'),('benefitNature','利益性质')]:
            if len({str(r.get(field)) for r in rows})>1:
                differences.append(f'{label}存在差异；当前结果不能无条件排名')
        if any(not any(r.get('versionId')==v and r.get('irr') is not None for r in rows) for v in version_ids):
            differences.append('部分产品缺少当前条件下可展示的收益结果')
        source_ids={sid for v in versions for sid in v.get('sourceIds') or []}
        source_ids.update(sid for f in facts if f['versionId'] in version_ids for sid in f.get('sourceIds') or [])
        source_ids.update(sid for r in rows for sid in r.get('sourceIds') or [])
        return {'products':versions,'dimensions':dimensions,'scenarios':rows,'differences':differences,
                'sources':_sources(conn,batch,source_ids),
                'limitations':['当前可售待核；本页用于内部研究。','IRR为保单年度现金流计算，不是正式报价。','保证、演示及开发稿分列；无统一总分或公司价值排名。']}


def source_file(source_id):
    with get_db() as conn:
        batch=active_batch_id(conn)
        row=conn.execute('SELECT * FROM product_center_sources WHERE batch_id=? AND id=?',(batch,source_id)).fetchone()
        if not row:
            raise HTTPException(404,'当前发布中没有该资料')
        root=storage_root()
        path=root/row['entry']
        if path.is_symlink() or not path.is_file() or path.resolve().parent!=root/'files':
            raise HTTPException(404,'资料不可用')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise HTTPException(409,'资料完整性校验失败')
        return raw,json.loads(row['data_json'])


def source_text(source_id, page=1):
    """Authenticated page text fallback for browsers without an embedded PDF viewer."""
    raw, source = source_file(source_id)
    if source['mediaType'] != 'application/pdf':
        _bad('仅PDF提供页码文字预览；其他格式请下载原件')
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        count = len(reader.pages)
        if not 1 <= page <= count:
            _bad('PDF页码超出范围')
        selected = reader.pages[page - 1]
        # Bound decompression before text extraction; originals remain downloadable.
        content = selected.get_contents()
        if content is not None and len(content.get_data()) > 16 * 1024 * 1024:
            _bad('本页内容过大，请下载原件查看')
        text = selected.extract_text() or ''
        return {'source':source,'page':page,'pageCount':count,'text':text[:200000],
                'truncated':len(text)>200000}
    except HTTPException:
        raise
    except Exception:
        _bad('PDF文字无法读取，请下载原件查看；扫描页可能没有文字层')
