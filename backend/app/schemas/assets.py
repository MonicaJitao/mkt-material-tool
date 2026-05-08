"""ImageAsset schemas（落地方案 §5.5 / §9.5–9.7）。"""

from datetime import datetime

from pydantic import BaseModel


# ── 批量生成 ──────────────────────────────────────────────────────────────────

class ImageBatchRequest(BaseModel):
    """POST /api/campaigns/{id}/images/batches 请求体（落地方案 §9.5）。"""

    count: int = 4
    size: str = "16:9"
    model: str | None = None
    reference_asset_ids: list[str] = []


class ImageBatchItem(BaseModel):
    image_asset_id: str
    provider_task_id: str | None = None
    status: str
    progress: int = 0
    preview_url: str | None = None
    local_path: str | None = None
    error_message: str | None = None


class ImageBatchResponse(BaseModel):
    """POST /api/campaigns/{id}/images/batches 响应体（落地方案 §9.5）。"""

    batch_id: str
    status: str
    items: list[ImageBatchItem]


class ImageBatchStatusResponse(BaseModel):
    """GET /api/image-batches/{batch_id} 响应体（落地方案 §9.6）。"""

    batch_id: str
    status: str
    items: list[ImageBatchItem]


# ── 选择底图 ──────────────────────────────────────────────────────────────────

class ImageSelectRequest(BaseModel):
    """POST /api/campaigns/{id}/images/select 请求体（落地方案 §9.7）。"""

    image_asset_id: str


class ImageSelectResponse(BaseModel):
    campaign_id: str
    selected_image_id: str
    status: str


# ── 资产详情 ──────────────────────────────────────────────────────────────────

class ImageAssetOut(BaseModel):
    id: str
    campaign_id: str
    generation_task_id: str | None = None
    kind: str
    status: str
    progress: int
    provider_task_id: str | None = None
    remote_url: str | None = None
    local_path: str | None = None
    prompt_text: str | None = None
    model: str | None = None
    size: str | None = None
    width: int | None = None
    height: int | None = None
    error_message: str | None = None
    selected_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
