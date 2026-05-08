"""
Tuzi（图兔）Banana 异步生图 Provider（落地方案 §7）。

接口：
  POST {TUZI_API_BASE}/v1/videos   multipart/form-data 提交任务
  GET  {TUZI_API_BASE}/v1/videos/{task_id}  轮询状态

字段兼容：
  任务 ID：id / task_id / job_id
  结果 URL：video_url / url / image_url
  状态：queued / processing / completed / failed
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings


# ── 数据类 ────────────────────────────────────────────────────────────────────

@dataclass
class SubmitResult:
    provider_task_id: str
    status: str = "queued"
    progress: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class PollResult:
    provider_task_id: str
    status: str          # queued / processing / completed / failed
    progress: int = 0
    result_url: str | None = None
    error_message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


# ── 轮询超时配置（秒） ────────────────────────────────────────────────────────

_POLL_INTERVALS: dict[str, int] = {
    "1k": 10,
    "2k": 15,
    "4k": 20,
}
_DEFAULT_POLL_INTERVAL = 15
_MAX_POLL_SECONDS = 600  # 10 分钟


# ── Provider ──────────────────────────────────────────────────────────────────

class TuziProvider:
    """
    封装 Tuzi Banana 异步生图 API。
    API Key 仅在后端使用，不暴露给前端。
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str | None = None,
    ) -> None:
        self._api_key = settings.TUZI_API_KEY if api_key is None else api_key
        self._api_base = (settings.TUZI_API_BASE if api_base is None else api_base).rstrip("/")
        self._default_model = settings.TUZI_IMAGE_MODEL if default_model is None else default_model

        self._submit_timeout = httpx.Timeout(connect=30, read=300, write=300, pool=10)
        self._poll_timeout = httpx.Timeout(connect=10, read=60, write=10, pool=10)

    # ── 提交任务 ──────────────────────────────────────────────────────────────

    async def submit(
        self,
        prompt: str,
        size: str = "9:16",
        model: str | None = None,
        reference_images: list[tuple[str, bytes, str]] | None = None,
    ) -> SubmitResult:
        """
        提交一个生图任务。

        Args:
            prompt: 底图 prompt
            size: 比例，冒号格式，例如 "9:16"
            model: 模型名称，默认使用配置值
            reference_images: 参考图列表，每项为 (filename, bytes, content_type)

        Returns:
            SubmitResult，包含 provider_task_id
        """
        if not self._api_key:
            raise TuziConfigError("TUZI_API_KEY 未配置")

        normalized_size = normalize_size(size)
        used_model = normalize_model(model or self._default_model)

        multipart: list[tuple[str, Any]] = [
            ("model", (None, used_model)),
            ("prompt", (None, prompt)),
            ("size", (None, normalized_size)),
        ]

        if reference_images:
            for filename, data, content_type in reference_images:
                multipart.append(("input_reference", (filename, data, content_type)))

        async with httpx.AsyncClient(timeout=self._submit_timeout) as client:
            resp = await client.post(
                f"{self._api_base}/v1/videos",
                files=multipart,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )

        data = _parse_json(resp)
        _check_http_error(resp, data)

        task_id = _extract_task_id(data)
        if not task_id:
            raise TuziResponseError(f"响应中未找到任务 ID: {data}")

        return SubmitResult(
            provider_task_id=task_id,
            status=data.get("status", "queued"),
            progress=int(data.get("progress", 0)),
            raw=data,
        )

    # ── 轮询状态 ──────────────────────────────────────────────────────────────

    async def poll(self, provider_task_id: str) -> PollResult:
        """
        查询单个任务状态（单次轮询，不循环）。
        """
        if not self._api_key:
            raise TuziConfigError("TUZI_API_KEY 未配置")

        async with httpx.AsyncClient(timeout=self._poll_timeout) as client:
            resp = await client.get(
                f"{self._api_base}/v1/videos/{provider_task_id}",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )

        data = _parse_json(resp)
        _check_http_error(resp, data)

        status = _normalize_status(data.get("status", "queued"))
        progress = int(data.get("progress", 0))
        result_url = _extract_result_url(data) if status == "completed" else None
        error_message = data.get("error") or data.get("error_message") or data.get("message")
        if status == "failed" and not error_message:
            error_message = "生图任务失败"

        return PollResult(
            provider_task_id=provider_task_id,
            status=status,
            progress=progress,
            result_url=result_url,
            error_message=str(error_message) if error_message else None,
            raw=data,
        )

    # ── 批量提交 ──────────────────────────────────────────────────────────────

    async def submit_batch(
        self,
        prompt: str,
        count: int,
        size: str = "9:16",
        model: str | None = None,
        reference_images: list[tuple[str, bytes, str]] | None = None,
    ) -> list[SubmitResult | Exception]:
        """
        并发提交 count 个任务，返回结果列表（失败项为 Exception）。
        """
        tasks = [
            self.submit(prompt, size=size, model=model, reference_images=reference_images)
            for _ in range(count)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return list(results)


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def normalize_size(size: str) -> str:
    """
    将前端可能传入的 9x16 / 9X16 格式统一转为 9:16。
    已经是冒号格式则直接返回。
    """
    return re.sub(r"[xX×]", ":", size.strip())


def normalize_model(model: str) -> str:
    """
    兼容图像批量生成工具中的模型别名。

    Tuzi /v1/videos 使用 async 模型名；如果调用方传入旧模型名，
    这里统一映射到对应 async 版本。
    """
    model = model.strip()
    if model.endswith("-async"):
        return model
    table = {
        "gemini-3-pro-image-preview": "gemini-3-pro-image-preview-async",
        "gemini-3-pro-image-preview-hd": "gemini-3-pro-image-preview-2k-async",
        "gemini-3-pro-image-preview-2k": "gemini-3-pro-image-preview-2k-async",
        "gemini-3-pro-image-preview-4k": "gemini-3-pro-image-preview-4k-async",
    }
    return table.get(model, model)


def _extract_task_id(data: dict[str, Any]) -> str | None:
    """兼容 id / task_id / job_id。"""
    return data.get("id") or data.get("task_id") or data.get("job_id")


def _extract_result_url(data: dict[str, Any]) -> str | None:
    """兼容 video_url / url / image_url。"""
    return data.get("video_url") or data.get("url") or data.get("image_url")


def _normalize_status(raw: str) -> str:
    """将 Tuzi 返回的状态统一为 queued / processing / completed / failed。"""
    raw = raw.lower()
    if raw in {"queued", "pending", "waiting"}:
        return "queued"
    if raw in {"processing", "running", "in_progress"}:
        return "processing"
    if raw in {"completed", "succeeded", "success", "done"}:
        return "completed"
    if raw in {"failed", "error", "cancelled", "canceled"}:
        return "failed"
    return raw


def _parse_json(resp: httpx.Response) -> dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"_raw_text": resp.text}


def _check_http_error(resp: httpx.Response, data: dict[str, Any]) -> None:
    if resp.status_code >= 400:
        msg = data.get("message") or data.get("error") or resp.text
        raise TuziAPIError(
            f"Tuzi API 返回 {resp.status_code}: {msg}",
            status_code=resp.status_code,
        )


# ── 异常类 ────────────────────────────────────────────────────────────────────

class TuziError(Exception):
    """Tuzi Provider 基础异常。"""


class TuziConfigError(TuziError):
    """配置缺失（API Key 未设置等）。"""


class TuziAPIError(TuziError):
    """Tuzi API 返回 HTTP 错误。"""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class TuziResponseError(TuziError):
    """Tuzi API 响应格式异常。"""


# ── 单例 ──────────────────────────────────────────────────────────────────────

tuzi_provider = TuziProvider()
