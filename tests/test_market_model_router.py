import json
import os
import subprocess
import pytest
import run_market_research as w
from market_analysis.model_router import (
    ProviderUnavailable, availability_fallback, bailian_base_url, is_bailian,
    provider_environment, provider_name, reasoning_effort,
)

@pytest.fixture(autouse=True)
def provider_keys(monkeypatch):
    monkeypatch.setenv('KIMI_CODE_API_KEY', 'kimi-test-only')
    monkeypatch.setenv('DEEPSEEK_AUTH_TOKEN', 'deepseek-test-only')
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'sk-bailian-test-only')
    monkeypatch.setenv('ANTHROPIC_AUTH_TOKEN', 'old-unrelated-key')
    monkeypatch.setenv('AI_READONLY_TOKEN', 'internal-test-only')
    monkeypatch.delenv('BAILIAN_API_KEY', raising=False)
    monkeypatch.delenv('BAILIAN_ANTHROPIC_BASE_URL', raising=False)
    monkeypatch.delenv('MARKET_ANALYSIS_REASONING_EFFORT', raising=False)
    monkeypatch.delenv('ANTHROPIC_BASE_URL', raising=False)


def invoke(events):
    return w.invoke_claude('claude', 'test', model='k3-256k', telemetry=events,
                           max_turns='2', max_budget='3', timeout_seconds=120)


def outcome(subtype='success', error=False, message='', cost=0.1, code=0):
    return subprocess.CompletedProcess([], code, json.dumps({'subtype': subtype, 'is_error': error,
        'result': message or {'ack': True}, 'total_cost_usd': cost}), '')


def test_credentials_models_context_and_process_environment_are_isolated():
    before = dict(os.environ)
    kimi = provider_environment('k3-256k')
    deepseek = provider_environment('deepseek-flash')
    assert kimi['ANTHROPIC_BASE_URL'] == 'https://api.kimi.com/coding/'
    assert kimi['ANTHROPIC_API_KEY'] == 'kimi-test-only'
    assert 'ANTHROPIC_AUTH_TOKEN' not in kimi
    assert kimi['CLAUDE_CODE_MAX_CONTEXT_TOKENS'] == '262144'
    assert deepseek['ANTHROPIC_AUTH_TOKEN'] == 'deepseek-test-only'
    assert 'ANTHROPIC_API_KEY' not in deepseek
    assert deepseek['CLAUDE_CODE_MAX_CONTEXT_TOKENS'] == '1000000'
    assert deepseek['CLAUDE_CODE_AUTO_COMPACT_WINDOW'] == '786432'
    for env in (kimi, deepseek):
        assert not {'KIMI_CODE_API_KEY', 'DEEPSEEK_AUTH_TOKEN', 'AI_READONLY_TOKEN'} & env.keys()
    assert os.environ == before


def test_success_does_not_invoke_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(w.subprocess, 'run', lambda *a, **k: calls.append(k['env']['ANTHROPIC_BASE_URL']) or outcome())
    events = []
    assert invoke(events) == {'ack': True}
    assert calls == ['https://api.kimi.com/coding/']
    assert events[0]['model'] == 'k3-256k'


@pytest.mark.parametrize('message', ['API Error: 401 invalid key', 'API Error: 429 rate limit',
                                    'HTTP 503 unavailable', 'Connection error', 'API Error: 400 model not found'])
def test_availability_failure_falls_back_once_with_remaining_budget(monkeypatch, message):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs['env']))
        return outcome('error_during_execution', True, message, cost=0.25, code=1) if len(calls)==1 else outcome()
    monkeypatch.setattr(w.subprocess, 'run', run)
    events = []
    assert invoke(events) == {'ack': True}
    assert len(calls) == 2
    command, env = calls[1]
    assert command[command.index('--model')+1] == 'deepseek-flash[1m]'
    assert float(command[command.index('--max-budget-usd')+1]) == 2.75
    assert env['ANTHROPIC_AUTH_TOKEN'] == 'deepseek-test-only'
    assert events[-1]['fallbackFrom'] == 'k3-256k'
    assert events[-1]['provider'] == 'DeepSeek'


@pytest.mark.parametrize('subtype', ['error_max_budget_usd', 'error_max_turns', 'error_max_structured_output_retries'])
def test_cost_or_content_failures_do_not_switch_provider(monkeypatch, subtype):
    calls = []
    monkeypatch.setattr(w.subprocess, 'run', lambda *a, **k: calls.append(1) or outcome(subtype, True, 'API Error: 429', code=1))
    with pytest.raises(RuntimeError): invoke([])
    assert len(calls) == 1


def test_timeout_allows_fallback_within_same_stage_deadline(monkeypatch):
    calls=[]
    def run(command, **kwargs):
        calls.append(kwargs['timeout'])
        if len(calls)==1: raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        return outcome()
    monkeypatch.setattr(w.subprocess, 'run', run)
    events=[]
    invoke(events)
    assert calls[0] == 60 and calls[1] <= 120
    assert events[0]['status'] == 'timeout'
    assert events[1]['fallbackFrom'] == 'k3-256k'


def test_both_unavailable_stop_without_loop(monkeypatch):
    calls=[]
    monkeypatch.setattr(w.subprocess, 'run', lambda *a, **k: calls.append(1) or outcome('error_during_execution',True,'API Error: 503',code=1))
    with pytest.raises(ProviderUnavailable): invoke([])
    assert len(calls)==2


def test_invalid_json_is_not_a_channel_outage(monkeypatch):
    calls=[]
    monkeypatch.setattr(w.subprocess, 'run', lambda *a, **k: calls.append(1) or subprocess.CompletedProcess([],0,'not JSON',''))
    with pytest.raises(RuntimeError):invoke([])
    assert len(calls)==1

BAILIAN_ENDPOINT = 'https://dashscope.aliyuncs.com/apps/anthropic'
LEAKED_KEYS = {'DASHSCOPE_API_KEY', 'BAILIAN_API_KEY', 'MARKET_ANALYSIS_BAILIAN_API_KEY',
               'KIMI_CODE_API_KEY', 'DEEPSEEK_AUTH_TOKEN', 'AI_READONLY_TOKEN',
               'ZHIHU_ACCESS_SECRET', 'MARKET_ANALYSIS_HERMES_API_KEY'}


def invoke_bailian(events, **kwargs):
    return w.invoke_claude('claude', 'test', model='qwen3.8-max', telemetry=events,
                           max_turns='2', max_budget='3', timeout_seconds=120, **kwargs)


def test_bailian_environment_isolates_credentials_and_pins_effort():
    before = dict(os.environ)
    env = provider_environment('qwen3.8-max')
    assert env['ANTHROPIC_BASE_URL'] == BAILIAN_ENDPOINT
    assert env['ANTHROPIC_AUTH_TOKEN'] == 'sk-bailian-test-only'
    assert 'ANTHROPIC_API_KEY' not in env
    assert env['ANTHROPIC_MODEL'] == 'qwen3.8-max'
    assert env['CLAUDE_CODE_EFFORT_LEVEL'] == 'high'
    assert env['CLAUDE_CODE_MAX_CONTEXT_TOKENS'] == '1000000'
    assert env['CLAUDE_CODE_AUTO_COMPACT_WINDOW'] == '786432'
    assert env['CLAUDE_CODE_DISABLE_1M_CONTEXT'] == '0'
    for key in ('ANTHROPIC_DEFAULT_OPUS_MODEL', 'ANTHROPIC_DEFAULT_SONNET_MODEL',
                'ANTHROPIC_DEFAULT_HAIKU_MODEL', 'CLAUDE_CODE_SUBAGENT_MODEL'):
        assert env[key] == 'qwen3.8-max'
    assert not LEAKED_KEYS & env.keys()
    assert os.environ == before


def test_bailian_provider_label_and_single_provider_routing():
    assert is_bailian('qwen3.8-max') and is_bailian('qwen3.8-max[1m]')
    assert is_bailian('qwen3.8-max-0902')
    assert not is_bailian('k3-256k') and not is_bailian('deepseek-flash')
    assert provider_name('qwen3.8-max') == '阿里百炼'
    assert provider_name('k3-256k') == 'Kimi Code'
    assert provider_name('deepseek-flash') == 'DeepSeek'
    assert availability_fallback('qwen3.8-max') is None
    assert availability_fallback('k3-256k') == 'deepseek-flash'


def test_bailian_base_url_never_ends_with_v1(monkeypatch):
    assert bailian_base_url() == BAILIAN_ENDPOINT
    monkeypatch.setenv('BAILIAN_ANTHROPIC_BASE_URL',
                       'https://ws-1.cn-beijing.maas.aliyuncs.com/apps/anthropic/v1/')
    assert bailian_base_url() == 'https://ws-1.cn-beijing.maas.aliyuncs.com/apps/anthropic'
    assert provider_environment('qwen3.8-max')['ANTHROPIC_BASE_URL'] == \
        'https://ws-1.cn-beijing.maas.aliyuncs.com/apps/anthropic'


def test_reasoning_effort_defaults_high_and_rejects_unknown_values(monkeypatch):
    assert reasoning_effort() == 'high'
    monkeypatch.setenv('MARKET_ANALYSIS_REASONING_EFFORT', 'MEDIUM')
    assert reasoning_effort() == 'medium'
    assert provider_environment('qwen3.8-max')['CLAUDE_CODE_EFFORT_LEVEL'] == 'medium'
    monkeypatch.setenv('MARKET_ANALYSIS_REASONING_EFFORT', 'ultra-bogus')
    assert reasoning_effort() == 'high'
    assert provider_environment('qwen3.8-max')['CLAUDE_CODE_EFFORT_LEVEL'] == 'high'


def test_bailian_requires_own_credential_and_never_borrows_other_providers(monkeypatch):
    monkeypatch.delenv('DASHSCOPE_API_KEY', raising=False)
    with pytest.raises(ProviderUnavailable):
        provider_environment('qwen3.8-max')
    monkeypatch.setenv('ANTHROPIC_BASE_URL', BAILIAN_ENDPOINT)
    assert provider_environment('qwen3.8-max')['ANTHROPIC_AUTH_TOKEN'] == 'old-unrelated-key'
    monkeypatch.setenv('ANTHROPIC_BASE_URL', 'https://api.kimi.com/coding/')
    with pytest.raises(ProviderUnavailable):
        provider_environment('qwen3.8-max')


@pytest.mark.parametrize('message', ['API Error: 401 invalid_api_key',
                                     'API Error: 429 Throttling.RateQuota',
                                     'HTTP 403 AccessDenied', 'Arrearage: account is overdue',
                                     'Flow control triggered'])
def test_bailian_outage_raises_without_switching_provider(monkeypatch, message):
    calls = []
    monkeypatch.setattr(w.subprocess, 'run',
                        lambda *a, **k: calls.append(k['env']['ANTHROPIC_BASE_URL'])
                        or outcome('error_during_execution', True, message, code=1))
    with pytest.raises(ProviderUnavailable):
        invoke_bailian([])
    assert calls == [BAILIAN_ENDPOINT]


def test_bailian_uses_full_stage_timeout_and_passes_model_through(monkeypatch):
    seen = {}

    def run(command, **kwargs):
        seen['timeout'] = kwargs['timeout']
        seen['model'] = command[command.index('--model') + 1]
        seen['effort'] = kwargs['env'].get('CLAUDE_CODE_EFFORT_LEVEL')
        return outcome()

    monkeypatch.setattr(w.subprocess, 'run', run)
    events = []
    assert invoke_bailian(events) == {'ack': True}
    assert seen['model'] == 'qwen3.8-max'
    assert seen['effort'] == 'high'
    assert seen['timeout'] == 120
    assert events[0]['provider'] == '阿里百炼'
    assert events[0]['model'] == 'qwen3.8-max'


def test_bailian_budget_cap_never_triggers_cross_provider_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(w.subprocess, 'run',
                        lambda *a, **k: calls.append(1)
                        or outcome('error_max_budget_usd', True, 'API Error: 429', cost=9.0, code=1))
    with pytest.raises(w.ModelBudgetExceeded):
        invoke_bailian([])
    assert len(calls) == 1

