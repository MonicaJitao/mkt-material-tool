"""
Claude Anthropic-compatible Provider（落地方案 §关键技术决策）。

使用 httpx 直接调用 Anthropic Messages API，无需安装 anthropic SDK。
ANTHROPIC_BASE_URL 可配置，支持中转站接入。
"""

import httpx

from app.core.config import settings


class ClaudeProvider:
    """调用 Anthropic Messages API 的异步 Provider。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.base_url = (base_url or settings.ANTHROPIC_BASE_URL).rstrip("/")
        self.model = model or settings.ANTHROPIC_MODEL
        self.max_tokens = max_tokens or settings.ANTHROPIC_MAX_TOKENS

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

        raise ValueError(f"Claude 响应中无文本内容: {data}")
