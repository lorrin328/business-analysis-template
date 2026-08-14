import json
from urllib.parse import parse_qs, urlsplit

import pytest

import run_market_research
from market_analysis import zhihu_api


class _Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit):
        return self.payload


def test_zhihu_search_uses_official_bearer_api_without_exposing_secret(monkeypatch):
    captured = {}
    monkeypatch.setenv("ZHIHU_ACCESS_SECRET", "test-secret-not-production")

    def fake_open(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timestamp"] = request.get_header("X-request-timestamp")
        captured["timeout"] = timeout
        return _Response({"data": []})

    monkeypatch.setattr(zhihu_api, "urlopen", fake_open)
    assert zhihu_api.search_zhihu("寿险 新模式", timeout_seconds=9) == {"data": []}
    parsed = urlsplit(captured["url"])
    assert parsed.scheme == "https"
    assert parsed.netloc == "developer.zhihu.com"
    assert parsed.path == "/api/v1/content/zhihu_search"
    assert parse_qs(parsed.query)["Query"] == ["寿险 新模式"]
    assert captured["authorization"] == "Bearer test-secret-not-production"
    assert captured["timestamp"].isdigit()
    assert captured["timeout"] == 9


def test_zhihu_candidates_are_conservative_c_level_direct_pages_only():
    payload = {
        "data": [
            {
                "title": "寿险渠道正在发生哪些变化？",
                "url": "https://www.zhihu.com/question/123/answer/456?utm_source=test",
                "snippet": "保险公司开始探索新的客户服务与渠道协同模式。",
                "author": {"name": "某保险研究者"},
                "created_at": 1786000000,
            },
            {
                "title": "不允许使用搜索结果页",
                "url": "https://www.zhihu.com/search?q=寿险",
                "snippet": "该条目不应进入候选来源。",
            },
            {
                "title": "不允许外部站点",
                "url": "https://example.com/article/1",
                "snippet": "该条目也不应进入候选来源。",
            },
        ]
    }
    candidates = zhihu_api.parse_zhihu_candidates(payload, section="peers", query="寿险渠道")
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["url"] == "https://www.zhihu.com/question/123/answer/456"
    assert candidate["sourceType"] == "media"
    assert candidate["sourceLevel"] == "C"
    assert candidate["publisher"] == "某保险研究者"
    assert candidate["claim"] == candidate["excerpt"]
    assert len(candidate["excerpt"]) <= 50
    assert candidate["discoveryChannel"] == "zhihu_official_api"


def test_zhihu_scout_is_disabled_without_both_flag_and_secret(monkeypatch):
    monkeypatch.setenv("MARKET_ANALYSIS_ZHIHU_ENABLED", "1")
    monkeypatch.delenv("ZHIHU_ACCESS_SECRET", raising=False)
    candidates, summary = zhihu_api.scout_zhihu_sources([])
    assert candidates == []
    assert summary == {
        "enabled": False,
        "status": "disabled",
        "queryCount": 0,
        "candidateCount": 0,
    }


def test_zhihu_scout_degrades_per_query_without_leaking_response(monkeypatch):
    monkeypatch.setenv("MARKET_ANALYSIS_ZHIHU_ENABLED", "1")
    monkeypatch.setenv("ZHIHU_ACCESS_SECRET", "test-secret-not-production")
    monkeypatch.setenv("MARKET_ANALYSIS_ZHIHU_MAX_QUERIES", "2")
    calls = []

    def fake_search(query, **_kwargs):
        calls.append(query)
        if len(calls) == 1:
            return {
                "results": [{
                    "title": "分红险需求变化观察",
                    "link": "https://zhuanlan.zhihu.com/p/123456",
                    "summary": "居民长期储蓄需求正在影响保险产品讨论。",
                }]
            }
        raise zhihu_api.ZhihuApiError("Zhihu API returned HTTP 429")

    monkeypatch.setattr(zhihu_api, "search_zhihu", fake_search)
    candidates, summary = zhihu_api.scout_zhihu_sources([])
    assert len(candidates) == 1
    assert summary["status"] == "partial"
    assert summary["queryCount"] == 2
    assert summary["candidateCount"] == 1
    assert summary["failureCount"] == 1
    assert summary["failures"] == ["Zhihu API returned HTTP 429"]


def test_zhihu_api_http_error_reports_status_only(monkeypatch):
    monkeypatch.setenv("ZHIHU_ACCESS_SECRET", "test-secret-not-production")

    def fake_open(request, timeout):
        del request, timeout
        raise zhihu_api.HTTPError("https://developer.zhihu.com", 401, "Unauthorized", {}, None)

    monkeypatch.setattr(zhihu_api, "urlopen", fake_open)
    with pytest.raises(zhihu_api.ZhihuApiError, match="HTTP 401") as exc_info:
        zhihu_api.search_zhihu("寿险")
    assert "test-secret" not in str(exc_info.value)


def test_source_scout_merges_zhihu_api_and_flash_candidates(monkeypatch):
    zhihu_candidate = {
        "section": "peers",
        "queryTheme": "寿险渠道",
        "claim": "寿险机构正在讨论新的渠道协同模式。",
        "title": "寿险渠道协同观察",
        "publisher": "知乎作者",
        "url": "https://zhuanlan.zhihu.com/p/123456",
        "sourceType": "media",
        "sourceLevel": "C",
        "publishedAt": None,
        "excerpt": "寿险机构正在讨论新的渠道协同模式。",
        "discoveryChannel": "zhihu_official_api",
    }
    flash_payload = {
        "queryCount": 8,
        "candidates": [{
            "id": "P1",
            "section": "regulation",
            "queryTheme": "监管政策",
            "claim": "监管部门发布新的制度文件。",
            "title": "制度文件",
            "publisher": "监管部门",
            "url": "https://www.gov.cn/example",
            "sourceType": "official",
            "sourceLevel": "A",
            "publishedAt": None,
            "excerpt": "监管部门发布新的制度文件。",
        }],
        "limitations": [],
        "wechatGaps": [],
    }
    monkeypatch.setattr(
        run_market_research,
        "scout_zhihu_sources",
        lambda _ledger: ([zhihu_candidate], {
            "enabled": True,
            "status": "success",
            "queryCount": 2,
            "candidateCount": 1,
            "failureCount": 0,
            "failures": [],
        }),
    )
    monkeypatch.setattr(run_market_research, "invoke_claude", lambda *_args, **_kwargs: flash_payload)

    def fake_verify(candidates):
        verified = []
        for index, candidate in enumerate(candidates, start=1):
            row = dict(candidate)
            row["id"] = row.get("id") or f"P{index}"
            row["retrievedAt"] = "2026-08-14T00:00:00+08:00"
            row["contentHash"] = "a" * 64
            row["verification"] = {"status": "verified"}
            verified.append(row)
        return verified, []

    monkeypatch.setattr(run_market_research, "verify_source_candidates", fake_verify)
    evidence, summary = run_market_research.run_source_scout(
        "claude",
        [],
        [],
        model_plan={"scout": "deepseek-v4-flash"},
        telemetry=[],
        timeout_seconds=60,
    )
    assert len(evidence) == 2
    assert summary["queryCount"] == 10
    assert summary["candidateCount"] == 2
    assert summary["zhihu"]["candidateCount"] == 1
    assert summary["zhihu"]["verifiedCount"] == 1
    assert summary["flashStatus"] == "success"
