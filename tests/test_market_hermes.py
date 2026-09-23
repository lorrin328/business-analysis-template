import io
import json

import pytest
from market_analysis import hermes
import run_market_research as runner


def test_hermes_error_never_exposes_response_or_key(monkeypatch):
    monkeypatch.setenv('MARKET_ANALYSIS_HERMES_API_KEY', 'test-secret')
    class Broken:
        def open(self, *args, **kwargs):
            raise RuntimeError('test-secret and sensitive server diagnostics')
    monkeypatch.setattr(hermes, 'build_opener', lambda *args: Broken())
    with pytest.raises(hermes.HermesError) as error:
        hermes.discover()
    assert str(error.value) == 'Hermes request failed: RuntimeError'


def test_redirect_refused():
    assert hermes._NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com') is None


def test_custom_model_cannot_inherit_hermes_secret(monkeypatch):
    from market_analysis.model_router import provider_environment
    monkeypatch.setenv('MARKET_ANALYSIS_HERMES_API_KEY', 'test-secret')
    monkeypatch.setenv('MARKET_ANALYSIS_HERMES_KEY_FILE', '/private/key')
    env = provider_environment('custom')
    assert 'MARKET_ANALYSIS_HERMES_API_KEY' not in env
    assert 'MARKET_ANALYSIS_HERMES_KEY_FILE' not in env


def test_wrong_cleartext_host_rejected_before_credentials(monkeypatch):
    monkeypatch.setenv('MARKET_ANALYSIS_HERMES_BASE_URL', 'http://example.com/v1')
    with pytest.raises(hermes.HermesError, match='Unapproved'):
        hermes.discover()


def test_hermes_receives_no_snapshot_or_history_and_parses(monkeypatch):
    monkeypatch.setenv('MARKET_ANALYSIS_HERMES_API_KEY', 'test-secret')
    class Capture:
        def open(self, req, timeout):
            body = json.loads(req.data)
            assert set(body) == {'model', 'stream', 'messages'}
            assert len(body['messages']) == 2
            return io.BytesIO(json.dumps({'choices': [{'message': {'content': '{"candidates":[],"queryCount":1}'}}]}).encode())
    monkeypatch.setattr(hermes, 'build_opener', lambda *args: Capture())
    assert hermes.discover()['queryCount'] == 1


def test_hermes_candidates_require_independent_verification(monkeypatch):
    monkeypatch.setenv('MARKET_ANALYSIS_HERMES_ENABLED', '1')
    candidate = dict(queryTheme='产品', section='peers', claim='事实', title='标题', publisher='保险公司',
                     url='https://example.com/a', sourceType='company', sourceLevel='B', excerpt='事实')
    monkeypatch.setattr(hermes, 'discover', lambda **kw: dict(queryCount=1,candidates=[candidate],limitations=[],wechatGaps=[]))
    monkeypatch.setattr(runner, 'scout_zhihu_sources', lambda _: ([], {}))
    monkeypatch.setattr(runner, 'invoke_claude', lambda *a, **kw: dict(queryCount=0,candidates=[],limitations=[],wechatGaps=[]))
    def reject(rows):
        assert rows[0]['discoveryChannel'] == 'hermes'
        return [], [dict(category='excerpt_unmatched')]
    monkeypatch.setattr(runner, 'verify_source_candidates', reject)
    evidence, summary = runner.run_source_scout('', [], [], model_plan={'scout':'test'}, telemetry=[], timeout_seconds=20)
    assert evidence == []
    assert summary['hermes']['candidateCount'] == 1
    assert summary['hermes']['verifiedCount'] == 0


def test_hermes_failure_preserves_original_scout(monkeypatch):
    monkeypatch.setenv('MARKET_ANALYSIS_HERMES_ENABLED', '1')
    def fail(**kw):
        raise hermes.HermesError('unavailable')
    monkeypatch.setattr(hermes, 'discover', fail)
    monkeypatch.setattr(runner, 'scout_zhihu_sources', lambda _: ([], {}))
    monkeypatch.setattr(runner, 'invoke_claude', lambda *a, **kw: dict(queryCount=2,candidates=[],limitations=[],wechatGaps=[]))
    monkeypatch.setattr(runner, 'verify_source_candidates', lambda rows: ([], []))
    _, summary = runner.run_source_scout('', [], [], model_plan={'scout':'test'}, telemetry=[], timeout_seconds=20)
    assert summary['hermes']['status'] == 'degraded'
    assert summary['flashStatus'] == 'success'
    assert summary['queryCount'] == 2
