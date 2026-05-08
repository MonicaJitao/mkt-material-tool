"""
素材文件读取路由（落地方案 §9.11）。

Agent B 实现：
  GET /api/assets/{asset_id}/file   返回底图文件流
  GET /api/assets/{asset_id}        返回底图元数据
  GET /api/campaigns/{campaign_id}/assets  列出活动的所有底图
"""

import mimetypes
import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response

from app.core.errors import AppError, NotFoundError
from app.db.models import ImageAsset
from app.db.session import get_db
from app.schemas.assets import ImageAssetOut
from app.schemas.common import ApiResponse
from app.services.storage_service import storage_service
from sqlalchemy.orm import Session

router = APIRouter(tags=["assets"])


# ── GET /api/assets/{asset_id}/file ──────────────────────────────────────────

@router.get("/api/assets/{asset_id}/file")
async def get_asset_file(asset_id: str, db: Session = Depends(get_db)):
    """
    返回底图文件流。
    前端用此 URL 作为 <img src> 或 preview_url。
    """
    asset = db.get(ImageAsset, asset_id)
    if asset is None:
        raise NotFoundError("ImageAsset", asset_id)

    if not asset.local_path:
        raise AppError(
            code="ASSET_NOT_DOWNLOADED",
            message="底图尚未下载到本地",
            status_code=404,
        )

    abs_path = storage_service.absolute_path(asset.local_path)
    if not abs_path.exists():
        raise AppError(
            code="ASSET_FILE_MISSING",
            message="底图文件不存在，可能已被删除",
            status_code=404,
        )

    media_type = _guess_media_type(str(abs_path))
    return FileResponse(path=str(abs_path), media_type=media_type)


# ── GET /api/assets/{asset_id} ────────────────────────────────────────────────

@router.get("/api/assets/{asset_id}", response_model=ApiResponse[ImageAssetOut])
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    """返回底图元数据。"""
    asset = db.get(ImageAsset, asset_id)
    if asset is None:
        raise NotFoundError("ImageAsset", asset_id)

    out = ImageAssetOut(
        id=asset.id,
        campaign_id=asset.campaign_id,
        generation_task_id=asset.generation_task_id,
        kind=asset.kind,
        status=asset.status,
        progress=asset.progress,
        provider_task_id=asset.provider_task_id,
        remote_url=asset.remote_url,
        local_path=asset.local_path,
        prompt_text=asset.prompt_text,
        model=asset.model,
        size=asset.size,
        width=asset.width,
        height=asset.height,
        error_message=asset.error_message,
        selected_at=asset.selected_at,
        created_at=asset.created_at,
    )
    return ApiResponse.success(out)


# ── GET /api/campaigns/{campaign_id}/assets ───────────────────────────────────

@router.get(
    "/api/campaigns/{campaign_id}/assets",
    response_model=ApiResponse[dict],
)
def list_campaign_assets(
    campaign_id: str,
    kind: str | None = None,
    db: Session = Depends(get_db),
):
    """列出活动的所有底图（可按 kind 过滤：candidate / selected）。"""
    q = db.query(ImageAsset).filter(ImageAsset.campaign_id == campaign_id)
    if kind:
        q = q.filter(ImageAsset.kind == kind)
    assets = q.order_by(ImageAsset.created_at).all()

    items = [
        ImageAssetOut(
            id=a.id,
            campaign_id=a.campaign_id,
            generation_task_id=a.generation_task_id,
            kind=a.kind,
            status=a.status,
            progress=a.progress,
            provider_task_id=a.provider_task_id,
            remote_url=a.remote_url,
            local_path=a.local_path,
            prompt_text=a.prompt_text,
            model=a.model,
            size=a.size,
            width=a.width,
            height=a.height,
            error_message=a.error_message,
            selected_at=a.selected_at,
            created_at=a.created_at,
        )
        for a in assets
    ]
    return ApiResponse.success({"items": [i.model_dump() for i in items]})


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _guess_media_type(path: str) -> str:
    mt, _ = mimetypes.guess_type(path)
    return mt or "application/octet-stream"
