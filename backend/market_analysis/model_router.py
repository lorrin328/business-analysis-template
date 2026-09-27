"""Isolated Claude Code provider environments and conservative availability failover."""
from __future__ import annotations
import json
import os
import re


class ProviderUnavailable(RuntimeError):
    """A transport/auth/provider failure, not content validation or a local cost cap."""


PROVIDER_BAILIAN = '阿里百炼'
PROVIDER_KIMI = 'Kimi Code'
PROVIDER_DEEPSEEK = 'DeepSeek'

# 阿里百炼 Anthropic 兼容端点（按量计费，华北2-北京）。
# base_url 只能到 /apps/anthropic；追加 /v1 会让 Claude Code 的模型发现
# 拼出 /v1/v1/models 并返回 404。百炼该端点只提供 /v1/messages。
BAILIAN_DEFAULT_BASE_URL = 'https://dashscope.aliyuncs.com/apps/anthropic'
BAILIAN_MODEL_PREFIX = 'qwen3.8-max'
# qwen3.8-max 的思考力度合法取值为 xhigh/medium/low，百炼会把 high 与 max
# 映射为 xhigh。本项目固定 high，等效于该模型最高档，且不会因取值非法被拒。
BAILIAN_EFFORT_DEFAULT = 'high'
BAILIAN_EFFORT_ALLOWED = frozenset({'low', 'medium', 'high', 'xhigh', 'max'})
# qwen3.8-max 上下文 1,000,000；思考模式下最大输入 983,616，
# 压缩窗口沿用已在生产验证过的 786432。
BAILIAN_CONTEXT_TOKENS = '1000000'
BAILIAN_COMPACT_WINDOW = '786432'
BAILIAN_CREDENTIAL_KEYS = ('DASHSCOPE_API_KEY', 'BAILIAN_API_KEY', 'MARKET_ANALYSIS_BAILIAN_API_KEY')

# 仅在明确配置了跨通道备份时才允许自动换供应商；
# 预算上限与内容门禁永远不触发跨通道重试。
LEGACY_AVAILABILITY_FALLBACK = {'k3-256k': 'deepseek-flash'}

SCRUBBED_KEYS = (
    'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN',
    'KIMI_CODE_API_KEY', 'DEEPSEEK_AUTH_TOKEN',
    'AI_READONLY_TOKEN', 'ZHIHU_ACCESS_SECRET',
    'MARKET_ANALYSIS_HERMES_API_KEY', 'MARKET_ANALYSIS_HERMES_KEY_FILE',
) + BAILIAN_CREDENTIAL_KEYS

DEFAULT_MODEL_KEYS = (
    'ANTHROPIC_DEFAULT_FABLE_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL',
    'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL',
    'ANTHROPIC_SMALL_FAST_MODEL', 'CLAUDE_CODE_SUBAGENT_MODEL',
)


def is_bailian(model: str) -> bool:
    """True for 百炼 qwen3.8-max routes, with or without the 1M context suffix."""
    name = (model or '').strip()
    if name.endswith('[1m]'):
        name = name[:-4]
    return name.startswith(BAILIAN_MODEL_PREFIX)


def provider_name(model: str) -> str:
    if is_bailian(model):
        return PROVIDER_BAILIAN
    return PROVIDER_KIMI if model == 'k3-256k' else PROVIDER_DEEPSEEK


def availability_fallback(model: str) -> str | None:
    """Cross-provider retry target, only for channels with a configured backup."""
    if is_bailian(model):
        return None
    return LEGACY_AVAILABILITY_FALLBACK.get(model)


def reasoning_effort() -> str:
    """思考深度；未知取值一律回到 high，不把非法值送给百炼。"""
    value = os.getenv('MARKET_ANALYSIS_REASONING_EFFORT', '').strip().lower()
    return value if value in BAILIAN_EFFORT_ALLOWED else BAILIAN_EFFORT_DEFAULT


def bailian_base_url() -> str:
    """Bailian Anthropic-compatible endpoint, never ending in /v1."""
    url = os.getenv('BAILIAN_ANTHROPIC_BASE_URL', '').strip() or BAILIAN_DEFAULT_BASE_URL
    url = url.rstrip('/')
    while url.lower().endswith('/v1'):
        url = url[:-3].rstrip('/')
    return url


def _is_bailian_host(url: str) -> bool:
    host = re.sub(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', '', (url or '').strip()).split('/')[0]
    return host == 'aliyuncs.com' or host.endswith('.aliyuncs.com')


def bailian_credential(env: dict[str, str]) -> str:
    for key in BAILIAN_CREDENTIAL_KEYS:
        token = (env.get(key) or '').strip()
        if token:
            return token
    # 与 DeepSeek 路由一致：仅当环境端点确属百炼域名时，
    # 才接受通用 ANTHROPIC_AUTH_TOKEN，避免把其他供应商凭据发往百炼。
    if not os.getenv('BAILIAN_ANTHROPIC_BASE_URL', '').strip() \
            and _is_bailian_host(env.get('ANTHROPIC_BASE_URL', '')):
        return (env.get('ANTHROPIC_AUTH_TOKEN') or '').strip()
    return ''


def provider_environment(model: str) -> dict[str, str]:
    env = os.environ.copy()
    # Hermes credentials are never needed by any model CLI, including custom routes.
    env.pop('MARKET_ANALYSIS_HERMES_API_KEY', None)
    env.pop('MARKET_ANALYSIS_HERMES_KEY_FILE', None)
    effort = ''
    if is_bailian(model):
        token = bailian_credential(env)
        if not token:
            raise ProviderUnavailable('Bailian credential is not configured')
        endpoint = bailian_base_url()
        compact, context = BAILIAN_COMPACT_WINDOW, BAILIAN_CONTEXT_TOKENS
        effort = reasoning_effort()
    elif model == 'k3-256k':
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
    for key in SCRUBBED_KEYS:
        env.pop(key, None)
    selector = 'deepseek-flash[1m]' if model.startswith('deepseek-flash') else model
    env.update(ANTHROPIC_BASE_URL=endpoint, ANTHROPIC_API_KEY=token,
               ANTHROPIC_MODEL=selector, CLAUDE_CODE_AUTO_COMPACT_WINDOW=compact,
               CLAUDE_CODE_MAX_CONTEXT_TOKENS=context, CLAUDE_CODE_DISABLE_1M_CONTEXT='0')
    if model.startswith('deepseek-flash') or is_bailian(model):
        # 百炼与 DeepSeek 均以 Authorization: Bearer 鉴权，不能同时保留 x-api-key。
        env['ANTHROPIC_AUTH_TOKEN'] = token
        env.pop('ANTHROPIC_API_KEY', None)
    if effort:
        env['CLAUDE_CODE_EFFORT_LEVEL'] = effort
    for key in DEFAULT_MODEL_KEYS:
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
        r'|request timed out|unable to connect|service unavailable'
        r'|access[_ ]?denied|arrearage|flow[ _]?control|throttl', message, re.I))
