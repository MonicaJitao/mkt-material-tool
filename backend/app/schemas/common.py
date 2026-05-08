"""统一响应包装与错误结构（落地方案 §9）。"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    error: ErrorDetail | None = None

    @classmethod
    def success(cls, data: T) -> "ApiResponse[T]":
        return cls(ok=True, data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str, details: dict | None = None) -> "ApiResponse[None]":
        return cls(
            ok=False,
            data=None,
            error=ErrorDetail(code=code, message=message, details=details or {}),
        )
