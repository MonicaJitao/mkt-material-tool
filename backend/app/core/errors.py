from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """业务异常，统一映射为契约错误结构。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


# ── 预定义错误码 ──────────────────────────────────────────────────────────────

class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            code="NOT_FOUND",
            message=f"{resource} '{resource_id}' 不存在",
            status_code=404,
        )


class InvalidTransitionError(AppError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            code="INVALID_STATE_TRANSITION",
            message=f"状态 '{current}' 不允许转换到 '{target}'",
            status_code=422,
        )


class ValidationError(AppError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
            details=details,
        )


# ── FastAPI 异常处理器 ────────────────────────────────────────────────────────

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "data": None,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "data": None,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误，请稍后重试",
                "details": {},
            },
        },
    )
