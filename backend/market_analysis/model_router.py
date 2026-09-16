"""Isolated Claude Code provider environments and conservative availability failover."""
from __future__ import annotations
import json
import os
import re


class ProviderUnavailable(RuntimeError):
    """A transport/auth/provider failure, not content validation or a local cost cap."""


def provider_name(model: str) -> str:
    return 'Kimi Code' if model == 'k3-256k' else 'DeepSeek'


def provider_environment(model: str) -> dict[str, str]:
    env = os.environ.copy()
    if model == 'k3-256k':
        token = env.get('KIMI_CODE_API_KEY', '').strip()
        if not token:
            raise ProviderUnavailable('Kimi Code credential is not configured')
        endpoint, compact, context = 'https://api.kimi.com/coding/', '262144', '262144'
    elif model in {'deepseek-flash', 'deepseek-flash[1m]'}:
        token = env.get('DEEPSEEK_AUTH_TOKEN', '').strip()
        if not token and env.get('ANTHROPIC_BASE_URL', 'https://api.deepseek.com/anthropic').rstrip('/') == 'https://api.deepseek.com/anthropic':
            token = env.get('ANTHROPIC_AUTH_TOKEN', '').strip()
        if not token:
            raise ProviderUnavailable('DeepSeek credential is not configured')
        endpoint, compact, context = 'https://api.deepseek.com/anthropic', '786432', '1000000'
    else:
        return env  # Existing custom model configurations keep their explicit endpoint.
    for key in ['ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN',
                'KIMI_CODE_API_KEY', 'DEEPSEEK_AUTH_TOKEN', 'AI_READONLY_TOKEN', 'ZHIHU_ACCESS_SECRET']:
        env.pop(key, None)
    selector = 'deepseek-flash[1m]' if model.startswith('deepseek-flash') else model
    env.update(ANTHROPIC_BASE_URL=endpoint, ANTHROPIC_API_KEY=token,
               ANTHROPIC_MODEL=selector, CLAUDE_CODE_AUTO_COMPACT_WINDOW=compact,
               CLAUDE_CODE_MAX_CONTEXT_TOKENS=context, CLAUDE_CODE_DISABLE_1M_CONTEXT='0')
    if model.startswith('deepseek-flash'):
        env['ANTHROPIC_AUTH_TOKEN'] = token
        env.pop('ANTHROPIC_API_KEY', None)
    for key in ['ANTHROPIC_DEFAULT_FABLE_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL',
                'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL',
                'ANTHROPIC_SMALL_FAST_MODEL', 'CLAUDE_CODE_SUBAGENT_MODEL']:
        env[key] = selector
    return env


def availability_failure(stdout: str, stderr: str) -> bool:
    try:
        result = json.loads(stdout)
    except (ValueError, TypeError):
        result = {}
    if not isinstance(result, dict):
        result = {}
    subtype = str(result.get('subtype') or '')
    if subtype in {'error_max_budget_usd', 'error_max_turns', 'error_max_structured_output_retries'}:
        return False
    message = str(result.get('result') or '') + ' ' + str(result.get('errors') or '') + ' ' + str(result.get('error') or '') + ' ' + stderr
    # Do not log raw diagnostics, which can include provider responses or credentials.
    return bool(re.search(
        r'(?:api error|http(?: status)?|status(?: code)?)\s*[:=]?\s*(?:400|401|402|403|404|408|429|5\d\d)\b'
        r'|authentication_error|permission_error|rate_limit_error|overloaded_error'
        r'|invalid.api.key|insufficient.quota|model.not.found|model.*not.available'
        r'|connection (?:error|refused|reset)|ECONNRESET|ETIMEDOUT|ENOTFOUND|fetch failed'
        r'|request timed out|unable to connect|service unavailable', message, re.I))
