"""Product research is deliberately inaccessible to module-granted non-admins."""
from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from auth import require_admin
from product_center import service
from services.audit_log import log_operation
from services.operation_lock import OperationLockError
from services.response import success_response

router = APIRouter(prefix='/api/product-center', tags=['product-center'], dependencies=[Depends(require_admin)])
Partition = Literal['guarantee', 'example', 'development']


@router.get('/products')
def products(q: str = Query('', max_length=200), channel: Literal['OTO', '证保'] | None = None,
             stage: Literal['formal', 'development', 'all'] = 'formal',
             responsibilityType: str | None = Query(None, max_length=200),
             benefitMechanism: str | None = Query(None, max_length=200)):
    return success_response(service.products(q, channel, stage, responsibilityType, benefitMechanism))


@router.get('/products/{version_id}')
def product(version_id: str):
    return success_response(service.product_detail(version_id))


@router.get('/products/{version_id}/scenarios')
def scenarios(version_id: str, partition: Partition = 'guarantee',
              payYears: int | None = Query(None, ge=0, le=100),
              horizonYear: int | None = Query(None, ge=0, le=200)):
    return success_response(service.scenarios(version_id, partition, payYears, horizonYear))


@router.get('/scenarios/{scenario_id}/cashflows')
def cashflows(scenario_id: str):
    return success_response(service.cashflows(scenario_id))


@router.post('/compare')
def compare(payload: dict = Body(...)):
    partition = payload.get('partition', 'guarantee')
    if partition not in ('guarantee', 'example', 'development'):
        raise HTTPException(400, '利益分区无效')
    for key in ('payYears', 'horizonYear'):
        value = payload.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 200):
            raise HTTPException(400, '比较条件无效')
    return success_response(service.compare(payload.get('versionIds'), partition, payload.get('payYears'), payload.get('horizonYear')))


@router.get('/sources/{source_id}/file')
def source_file(source_id: str, user=Depends(require_admin)):
    data, source = service.source_file(source_id)
    log_operation('product_center_source_access', user=user, detail={'sourceId': source_id})
    inline = source['mediaType'] in ('application/pdf', 'image/png', 'image/jpeg')
    headers = {'Cache-Control': 'no-store, private', 'Pragma': 'no-cache',
               'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "sandbox; default-src 'none'",
               'Content-Disposition': f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(source['filename'], safe='')}"}
    return Response(data, media_type=source['mediaType'], headers=headers)


@router.get('/sources/{source_id}/text')
def source_text(source_id: str, page: int = Query(1, ge=1, le=10000), user=Depends(require_admin)):
    result = service.source_text(source_id, page)
    log_operation('product_center_source_access', user=user, detail={'sourceId':source_id,'page':page})
    return success_response(result)


def _mutate(action, batch_id, user):
    try:
        result = getattr(service, action)(batch_id, user)
    except OperationLockError:
        raise HTTPException(409, '另一项数据维护正在执行，请稍后重试')
    return success_response(result)


@router.post('/imports/preview')
async def preview(file: UploadFile = File(...), user=Depends(require_admin)):
    chunks = []
    size = 0
    try:
        while block := await file.read(1024 * 1024):
            size += len(block)
            if size > service.MAX_PACKAGE_BYTES:
                raise HTTPException(413, '导入包超过100MB')
            chunks.append(block)
        result = await run_in_threadpool(service.preview_package, b''.join(chunks), user)
    except OperationLockError:
        raise HTTPException(409, '另一项数据维护正在执行，请稍后重试')
    except HTTPException:
        log_operation('product_center_preview', user=user, status='failed', detail={'bytes': size})
        raise
    finally:
        await file.close()
    return success_response(result)


@router.get('/imports')
def imports():
    return success_response(service.list_imports())


@router.get('/imports/{batch_id}')
def import_detail(batch_id: str):
    return success_response(service.import_detail(batch_id))


@router.post('/imports/{batch_id}/publish')
def publish(batch_id: str, user=Depends(require_admin)):
    return _mutate('publish', batch_id, user)


@router.post('/imports/{batch_id}/withdraw')
def withdraw(batch_id: str, user=Depends(require_admin)):
    return _mutate('withdraw', batch_id, user)
