"""HtmlPoster / HtmlVersion schemas（落地方案 §5.6–5.7 / §9.8–9.12）。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ── HTML 生成 ─────────────────────────────────────────────────────────────────

class HtmlGenerateRequest(BaseModel):
    """POST /api/campaigns/{id}/html/generate 请求体（落地方案 §9.8）。"""

    selected_image_id: str
    model: str | None = None


class ValidationResult(BaseModel):
    ok: bool
    issues: list[str] = []


class HtmlGenerateResponse(BaseModel):
    """POST /api/campaigns/{id}/html/generate 响应体（落地方案 §9.8）。"""

    poster_id: str
    version_id: str
    status: str
    preview_url: str
    validation: ValidationResult


# ── HTML 内容读取 ─────────────────────────────────────────────────────────────

class HtmlVersionContent(BaseModel):
    """GET /api/html/{version_id} 响应体（落地方案 §9.9）。"""

    version_id: str
    poster_id: str
    version_no: int
    source: str
    html: str
    created_at: datetime


# ── 保存手动编辑版本 ──────────────────────────────────────────────────────────

class HtmlVersionSaveRequest(BaseModel):
    """POST /api/html/{poster_id}/versions 请求体（落地方案 §9.10）。"""

    source: str = "manual_edit"
    html: str


class HtmlVersionSaveResponse(BaseModel):
    """POST /api/html/{poster_id}/versions 响应体（落地方案 §9.10）。"""

    poster_id: str
    version_id: str
    version_no: int
    validation: ValidationResult


# ── 版本列表 ──────────────────────────────────────────────────────────────────

class HtmlVersionOut(BaseModel):
    id: str
    poster_id: str
    version_no: int
    source: str
    html_path: str | None = None
    model: str | None = None
    validation: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HtmlPosterOut(BaseModel):
    id: str
    campaign_id: str
    selected_image_id: str | None = None
    title: str | None = None
    current_version_id: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    versions: list[HtmlVersionOut] = []

    model_config = {"from_attributes": True}
