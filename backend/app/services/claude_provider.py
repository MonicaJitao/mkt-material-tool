"""
LLM Provider — 支持 Anthropic 兼容接口的通用 Provider。

使用 httpx 直接调用 Anthropic Messages API，无需安装 anthropic SDK。
支持 Claude 和 DeepSeek（Anthropic 兼容格式），通过 auth_style 区分认证方式。
"""

import httpx

from app.core.config import settings


class LlmProvider:
    """调用 Anthropic Messages API 的异步 Provider，支持多种认证方式。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        auth_style: str = "x-api-key",
    ):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.base_url = (base_url or settings.ANTHROPIC_BASE_URL).rstrip("/")
        self.model = model or settings.ANTHROPIC_MODEL
        self.max_tokens = max_tokens or settings.ANTHROPIC_MAX_TOKENS
        self.auth_style = auth_style

    async def complete(
        self,
        system: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        调用 Anthropic Messages API，返回第一个 text block 的内容。

        Raises:
            httpx.HTTPStatusError: API 返回非 2xx 状态码。
            ValueError: 响应中无文本内容。
        """
        url = f"{self.base_url}/v1/messages"

        if self.auth_style == "bearer":
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        else:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }

        payload = {
            "model": model or self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_message}],
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        for block in data.get("content", []):
            if block.get("type") == "text":
                return block["text"]

        raise ValueError(f"LLM 响应中无文本内容: {data}")


# 向后兼容别名
ClaudeProvider = LlmProvider

# ── 模型 → Provider 配置映射 ──────────────────────────────────────────────────

_MODEL_CONFIGS: dict[str, dict] = {
    # Claude 模型 — 使用 settings 中的 Anthropic 默认配置
    "claude-sonnet-4-6": {"auth_style": "x-api-key"},
    "claude-opus-4-7": {"auth_style": "x-api-key"},
    # DeepSeek 模型 — 使用 Anthropic 兼容格式 + Bearer 认证
    "deepseek-v4-flash": {
        "auth_style": "bearer",
        "api_key_setting": "DEEPSEEK_API_KEY",
        "base_url_setting": "DEEPSEEK_BASE_URL",
    },
    "deepseek-v4-pro": {
        "auth_style": "bearer",
        "api_key_setting": "DEEPSEEK_API_KEY",
        "base_url_setting": "DEEPSEEK_BASE_URL",
    },
}


def get_provider(model: str | None = None) -> LlmProvider:
    """根据模型名创建对应的 LlmProvider。未匹配的模型默认走 Claude 配置。"""
    model = model or settings.ANTHROPIC_MODEL
    config = _MODEL_CONFIGS.get(model, {})
    auth_style = config.get("auth_style", "x-api-key")

    api_key = None
    base_url = None
    if auth_style == "bearer":
        api_key = getattr(settings, config.get("api_key_setting", ""), None)
        base_url = getattr(settings, config.get("base_url_setting", ""), None)

    return LlmProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
        auth_style=auth_style,
    )


def provider_name_for_model(model: str) -> str:
    """返回 provider 名称用于 GenerationTask 日志记录。"""
    config = _MODEL_CONFIGS.get(model, {})
    if config.get("auth_style") == "bearer":
        return "deepseek"
    return "claude"
