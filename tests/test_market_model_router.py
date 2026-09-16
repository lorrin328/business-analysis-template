import json
import os
import subprocess
import pytest
import run_market_research as w
from market_analysis.model_router import provider_environment, ProviderUnavailable

@pytest.fixture(autouse=True)
def provider_keys(monkeypatch):
    monkeypatch.setenv('KIMI_CODE_API_KEY', 'kimi-test-only')
    monkeypatch.setenv('DEEPSEEK_AUTH_TOKEN', 'deepseek-test-only')
    monkeypatch.setenv('ANTHROPIC_AUTH_TOKEN', 'old-unrelated-key')
    monkeypatch.setenv('AI_READONLY_TOKEN', 'internal-test-only')


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
