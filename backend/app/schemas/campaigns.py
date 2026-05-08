"""Campaign schemas（落地方案 §5.3 / §9.2–9.4）。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 创建活动 ──────────────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    """POST /api/campaigns 请求体（落地方案 §9.2）。"""

    project_name: str = Field(..., min_length=1, max_length=128)
    campaign_name: str = Field(..., min_length=1, max_length=128)
    template_id: str | None = None
    brief: dict[str, Any] | None = None


class CampaignCreateResponse(BaseModel):
    campaign_id: str
    status: str


# ── 方案确认 ──────────────────────────────────────────────────────────────────

class PlanApproveRequest(BaseModel):
    """POST /api/campaigns/{id}/plan/approve 请求体（落地方案 §9.4）。"""

    approved_plan: dict[str, Any]


class PlanApproveResponse(BaseModel):
    campaign_id: str
    status: str


# ── 方案生成响应（Agent C 实现，此处定义契约）────────────────────────────────

class PlanGenerateResponse(BaseModel):
    """POST /api/campaigns/{id}/plan/generate 响应体（落地方案 §9.3）。"""

    campaign_id: str
    task_id: str
    status: str
    structured_plan: dict[str, Any] | None = None


# ── 活动详情 ──────────────────────────────────────────────────────────────────

class CampaignOut(BaseModel):
    id: str
    project_id: str
    template_id: str | None = None
    name: str
    slug: str
    status: str
    failed_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    brief: dict[str, Any] | None = None
    structured_plan: dict[str, Any] | None = None
    approved_plan: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    items: list[CampaignOut]
