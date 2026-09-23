"""Keep WeChat research signals distinct from independently verified facts."""
from __future__ import annotations

from urllib.parse import urlsplit, parse_qsl


def safe_article_url(value) -> str:
    value = str(value or '').strip()
    try:
        u = urlsplit(value)
        if (u.scheme != 'https' or u.hostname != 'mp.weixin.qq.com' or u.username or u.password
                or u.port not in {None, 443} or not (u.path == '/s' or u.path.startswith('/s/'))):
            return ''
        # Only public article identity parameters; never retain session parameters.
        if any(k not in {'__biz', 'mid', 'idx', 'sn', 'chksm', 'scene', 'srcid'} for k, _ in parse_qsl(u.query)):
            return ''
        return value.split('#', 1)[0][:2000]
    except ValueError:
        return ''


def retain_leads(raw_leads: list, candidates: list, rejected: list) -> list[dict]:
    failures = {str(row.get('id')): row for row in rejected if isinstance(row, dict)}
    rows = list(raw_leads or [])
    for candidate in candidates:
        failure = failures.get(str(candidate.get('id')))
        if failure and failure.get('category') != 'duplicate' and safe_article_url(candidate.get('url')):
            rows.append({**candidate, 'accessNote': '独立原文核验未完成：' + str(failure.get('category', 'unknown'))})
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        claim = str(row.get('claim') or row.get('excerpt') or '').strip()[:240]
        title = str(row.get('title') or '').strip()[:120]
        publisher = str(row.get('publisher') or '').strip()[:100]
        if not claim or not title:
            continue
        url = safe_article_url(row.get('url'))
        identity = (url or title, claim)
        if identity in seen:
            continue
        seen.add(identity)
        result.append({'id': f'WL{len(result)+1}', 'title': title, 'publisher': publisher or '主体待核验',
                       'url': url, 'claim': claim, 'materialType': str(row.get('materialType') or 'unknown')[:40],
                       'accessNote': str(row.get('accessNote') or '待交叉核验；访问受限不等于内容错误')[:200],
                       'status': 'unresolved'})
        if len(result) >= 12:
            break
    return result


def apply_lead_reviews(report: dict, leads: list[dict]) -> None:
    """References must be independently fetched; semantic comparisons remain model analysis."""
    sources = {s.get('id'): s for s in report.get('sources', []) if isinstance(s, dict)}
    reviews = report.get('wechatLeadReviews') or []
    if not isinstance(reviews, list):
        reviews = []
    by_id = {r.get('leadId'): r for r in reviews if isinstance(r, dict) and isinstance(r.get('leadId'), str)}
    output = []
    for lead in leads:
        row = dict(lead)
        review = by_id.get(lead['id'], {})
        ids = review.get('evidenceIds') or []
        if not isinstance(ids, list):
            ids = []
        refs = [s for ident in ids if isinstance(ident, str) and (s := sources.get(ident))
                and (s.get('verification') or {}).get('status') == 'verified'
                and s.get('sourceType') != 'internal' and s.get('url') != lead.get('url')]
        status = review.get('status')
        assessment = str(review.get('assessment') or '').strip()[:240]
        allowed = status in {'supported', 'partial', 'conflicting'} and bool(refs) and bool(assessment)
        if status == 'supported':
            allowed = allowed and any(s.get('sourceLevel') in {'A', 'B'} for s in refs)
        row.update(status=status if allowed else 'unresolved', evidenceIds=[s['id'] for s in refs],
                   assessment=assessment if allowed else '现有证据尚不足以形成交叉比对结论；保留为研究参考。')
        output.append(row)
    report['wechatLeads'] = output
