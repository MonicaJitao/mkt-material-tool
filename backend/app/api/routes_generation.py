"""
底图批量生成路由（落地方案 §9.5–9.7）。

Agent B 实现：
  POST /api/campaigns/{campaign_id}/images/batches   批量提交生图任务
  GET  /api/image-batches/{batch_id}                 查询批次状态（触发 Tuzi 轮询）
  POST /api/campaigns/{campaign_id}/images/select    选择底图
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.state_machine import CampaignStatus, assert_valid_transition
from app.core.utils import new_id
from app.db.models import Campaign, GenerationTask, ImageAsset, Project, Template
from app.db.session import get_db
from app.schemas.assets import (
    ImageBatchItem,
    ImageBatchRequest,
    ImageBatchResponse,
    ImageBatchStatusResponse,
    ImageSelectRequest,
    ImageSelectResponse,
)
from app.schemas.common import ApiResponse
from app.services.image_provider_tuzi import (
    SubmitResult,
    TuziError,
    tuzi_provider,
)
from app.services.prompt_agent import PromptAgent
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])
_MAX_IMAGE_POLL_SECONDS = 1200


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_campaign_or_404(db: Session, campaign_id: str) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Campaign", campaign_id)
    return campaign


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project", project_id)
    return project


def _asset_to_item(asset: ImageAsset) -> ImageBatchItem:
    preview_url = f"/api/assets/{asset.id}/file" if asset.local_path else None
    return ImageBatchItem(
        image_asset_id=asset.id,
        provider_task_id=asset.provider_task_id,
        status=asset.status,
        progress=asset.progress,
        preview_url=preview_url,
        local_path=asset.local_path,
        error_message=asset.error_message,
    )


def _batch_overall_status(assets: list[ImageAsset]) -> str:
    """根据所有 slot 状态推断批次整体状态。"""
    statuses = {a.status for a in assets}
    if statuses <= {"completed", "failed"}:
        return "image_pending_selection"
    return "image_generating"


async def _ensure_image_prompt(
    *,
    db: Session,
    campaign: Campaign,
    template: Template | None,
    size: str,
) -> tuple[dict, str]:
    """
    确认方案后按需生成底图 prompt。

    /plan/approve 的接口契约只要求保存 approved_plan，前端不需要自行提供
    image_prompt；这里在创建底图批次前补齐 PromptAgent 产物，并写回活动记录。
    """
    approved_plan = json.loads(campaign.approved_plan_json) if campaign.approved_plan_json else {}
    image_prompt = approved_plan.get("image_prompt") or approved_plan.get("imagePrompt")
    if image_prompt:
        return approved_plan, str(image_prompt)

    brief = json.loads(campaign.brief_json) if campaign.brief_json else {}
    prompt_result = await PromptAgent().generate_prompts(
        approved_plan=approved_plan,
        brief=brief,
        size=size,
        template_image_prompt=template.image_prompt_template if template else None,
        template_html_prompt=template.html_prompt_template if template else None,
    )
    image_prompt = prompt_result.get("image_prompt") or prompt_result.get("imagePrompt")
    if not image_prompt:
        raise ValidationError("PromptAgent 未返回底图 prompt，无法创建底图批次")

    approved_plan.update(prompt_result)
    campaign.approved_plan_json = json.dumps(approved_plan, ensure_ascii=False)
    db.flush()
    return approved_plan, str(image_prompt)


# ── POST /api/campaigns/{campaign_id}/images/batches ─────────────────────────

@router.post(
    "/api/campaigns/{campaign_id}/images/batches",
    response_model=ApiResponse[ImageBatchResponse],
    status_code=201,
)
async def create_image_batch(
    campaign_id: str,
    body: ImageBatchRequest,
    db: Session = Depends(get_db),
):
    """
    批量提交底图生成任务。
    - 验证活动状态为 plan_approved（或 image_pending_selection，允许重新生成）
    - 并发提交 N 个 Tuzi 任务
    - 每个 slot 独立记录 provider_task_id 和状态
    - 更新活动状态为 image_generating
    """
    campaign = _get_campaign_or_404(db, campaign_id)

    allowed_statuses = {
        CampaignStatus.PLAN_APPROVED.value,
        CampaignStatus.IMAGE_PENDING_SELECTION.value,  # 重新生成
        CampaignStatus.FAILED.value,
    }
    if campaign.status not in allowed_statuses:
        raise ValidationError(
            f"活动状态 '{campaign.status}' 不允许发起底图生成，"
            f"需要 plan_approved 或 image_pending_selection"
        )

    project = _get_project_or_404(db, campaign.project_id)
    template = db.get(Template, campaign.template_id) if campaign.template_id else None

    # 获取或生成视觉方案对应的底图 prompt，前端不需要直接传 prompt。
    _, image_prompt = await _ensure_image_prompt(
        db=db,
        campaign=campaign,
        template=template,
        size=body.size,
    )

    # 计算批次号（同一活动的第几批）
    existing_tasks = (
        db.query(GenerationTask)
        .filter(
            GenerationTask.campaign_id == campaign_id,
            GenerationTask.task_type == "image_batch",
        )
        .count()
    )
    batch_no = existing_tasks + 1

    # 创建 GenerationTask
    task = GenerationTask(
        id=new_id("task"),
        campaign_id=campaign_id,
        task_type="image_batch",
        status="running",
        model=body.model or tuzi_provider._default_model,
        provider="tuzi",
        input_json=json.dumps(
            {
                "count": body.count,
                "size": body.size,
                "model": body.model,
                "reference_asset_ids": body.reference_asset_ids,
                "batch_no": batch_no,
            },
            ensure_ascii=False,
        ),
        prompt_text=image_prompt,
    )
    db.add(task)
    db.flush()

    # 创建 ImageAsset 占位记录
    assets: list[ImageAsset] = []
    for slot_no in range(1, body.count + 1):
        asset = ImageAsset(
            id=new_id("img"),
            campaign_id=campaign_id,
            generation_task_id=task.id,
            kind="candidate",
            status="queued",
            progress=0,
            prompt_text=image_prompt,
            model=body.model or tuzi_provider._default_model,
            size=body.size,
        )
        db.add(asset)
        assets.append(asset)
    db.flush()

    # 读取参考图（若有）
    reference_images: list[tuple[str, bytes, str]] = []
    for ref_id in body.reference_asset_ids:
        ref_asset = db.get(ImageAsset, ref_id)
        if ref_asset and ref_asset.local_path:
            try:
                data = await storage_service.read_file(ref_asset.local_path)
                ext = (ref_asset.local_path.rsplit(".", 1)[-1]) or "jpg"
                reference_images.append((f"reference.{ext}", data, f"image/{ext}"))
            except Exception as e:
                logger.warning("读取参考图 %s 失败: %s", ref_id, e)

    # 并发提交 Tuzi 任务
    submit_results = await tuzi_provider.submit_batch(
        prompt=image_prompt,
        count=body.count,
        size=body.size,
        model=body.model,
        reference_images=reference_images or None,
    )

    # 更新每个 slot 的 provider_task_id
    for asset, result in zip(assets, submit_results):
        if isinstance(result, Exception):
            asset.status = "failed"
            asset.error_message = str(result)
            logger.error("Slot %s 提交失败: %s", asset.id, result)
        else:
            asset.provider_task_id = result.provider_task_id
            asset.status = result.status
            asset.progress = result.progress

    # 更新活动状态
    assert_valid_transition(campaign.status, CampaignStatus.IMAGE_GENERATING.value)
    campaign.status = CampaignStatus.IMAGE_GENERATING.value
    campaign.failed_stage = None
    campaign.error_code = None
    campaign.error_message = None

    db.commit()
    for asset in assets:
        db.refresh(asset)

    return ApiResponse.success(
        ImageBatchResponse(
            batch_id=task.id,
            status="image_generating",
            items=[_asset_to_item(a) for a in assets],
        )
    )


# ── GET /api/image-batches/{batch_id} ────────────────────────────────────────

@router.get(
    "/api/image-batches/{batch_id}",
    response_model=ApiResponse[ImageBatchStatusResponse],
)
async def get_image_batch_status(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """
    查询批次状态，同时触发对 Tuzi 的轮询更新。
    - 对 queued/processing 的 slot 调用 Tuzi poll
    - completed 时下载图片到本地
    - 全部完成后更新活动状态为 image_pending_selection
    """
    task = db.get(GenerationTask, batch_id)
    if task is None:
        raise NotFoundError("GenerationTask", batch_id)

    assets: list[ImageAsset] = (
        db.query(ImageAsset)
        .filter(ImageAsset.generation_task_id == batch_id)
        .order_by(ImageAsset.created_at)
        .all()
    )

    campaign = _get_campaign_or_404(db, task.campaign_id)
    project = _get_project_or_404(db, campaign.project_id)

    # 对未完成的 slot 触发 Tuzi 轮询
    pending_assets = [
        a for a in assets
        if a.status in {"queued", "processing"} and a.provider_task_id
    ]

    for asset in pending_assets:
        created_at_utc = _coerce_utc(asset.created_at)
        elapsed_seconds = (datetime.now(timezone.utc) - created_at_utc).total_seconds()
        if elapsed_seconds > _MAX_IMAGE_POLL_SECONDS:
            asset.status = "failed"
            asset.error_message = "生图任务超过 10 分钟未完成，请重新生成一批"
            continue

        try:
            poll_result = await tuzi_provider.poll(asset.provider_task_id)
            asset.status = poll_result.status
            asset.progress = poll_result.progress

            if poll_result.status == "completed" and poll_result.result_url:
                asset.remote_url = poll_result.result_url
                # 下载图片到本地
                try:
                    data, ext = await storage_service.download_image(poll_result.result_url)
                    input_data = json.loads(task.input_json) if task.input_json else {}
                    batch_no = input_data.get("batch_no", 1)
                    slot_no = assets.index(asset) + 1
                    local_path = await storage_service.save_candidate_image(
                        project_slug=project.slug,
                        campaign_slug=campaign.slug,
                        batch_no=batch_no,
                        slot_no=slot_no,
                        data=data,
                        ext=ext,
                    )
                    asset.local_path = local_path
                except Exception as e:
                    logger.error("下载图片失败 asset=%s url=%s: %s", asset.id, poll_result.result_url, e)
                    asset.error_message = f"图片下载失败: {e}"
                    asset.status = "failed"

            elif poll_result.status == "failed":
                asset.error_message = poll_result.error_message or "生图任务失败"

        except TuziError as e:
            logger.error("轮询 Tuzi 失败 asset=%s: %s", asset.id, e)
            # 轮询失败不标记 slot 为 failed，保留当前状态等待下次轮询

    db.flush()

    # 检查是否全部完成
    all_done = all(a.status in {"completed", "failed"} for a in assets)
    if all_done and campaign.status == CampaignStatus.IMAGE_GENERATING.value:
        campaign.status = CampaignStatus.IMAGE_PENDING_SELECTION.value
        task.status = "completed"

    db.commit()
    for asset in assets:
        db.refresh(asset)

    overall_status = _batch_overall_status(assets)

    return ApiResponse.success(
        ImageBatchStatusResponse(
            batch_id=batch_id,
            status=overall_status,
            items=[_asset_to_item(a) for a in assets],
        )
    )


# ── POST /api/campaigns/{campaign_id}/images/select ──────────────────────────

@router.post(
    "/api/campaigns/{campaign_id}/images/select",
    response_model=ApiResponse[ImageSelectResponse],
)
async def select_image(
    campaign_id: str,
    body: ImageSelectRequest,
    db: Session = Depends(get_db),
):
    """
    用户选择一张底图。
    - 验证 asset 属于该活动且状态为 completed
    - 将 asset.kind 更新为 selected
    - 更新活动状态为 image_selected
    """
    campaign = _get_campaign_or_404(db, campaign_id)

    if campaign.status not in {
        CampaignStatus.IMAGE_PENDING_SELECTION.value,
        CampaignStatus.IMAGE_SELECTED.value,  # 允许重新选择
    }:
        raise ValidationError(
            f"活动状态 '{campaign.status}' 不允许选择底图，需要 image_pending_selection"
        )

    asset = db.get(ImageAsset, body.image_asset_id)
    if asset is None:
        raise NotFoundError("ImageAsset", body.image_asset_id)
    if asset.campaign_id != campaign_id:
        raise ValidationError("该底图不属于当前活动")
    if asset.status != "completed":
        raise ValidationError(f"底图状态为 '{asset.status}'，只能选择已完成的底图")
    if not asset.local_path:
        raise ValidationError("底图尚未下载到本地，无法选择")

    # 将之前选中的底图重置为 candidate
    db.query(ImageAsset).filter(
        ImageAsset.campaign_id == campaign_id,
        ImageAsset.kind == "selected",
    ).update({"kind": "candidate", "selected_at": None})

    # 标记新选中
    project = _get_project_or_404(db, campaign.project_id)
    data = await storage_service.read_file(asset.local_path)
    ext = (asset.local_path.rsplit(".", 1)[-1]) or "jpg"
    asset.local_path = await storage_service.save_selected_image(
        project_slug=project.slug,
        campaign_slug=campaign.slug,
        data=data,
        ext=ext,
    )
    asset.kind = "selected"
    asset.selected_at = datetime.now(timezone.utc)

    # 更新活动状态；重复选择时保持 image_selected。
    if campaign.status != CampaignStatus.IMAGE_SELECTED.value:
        assert_valid_transition(campaign.status, CampaignStatus.IMAGE_SELECTED.value)
        campaign.status = CampaignStatus.IMAGE_SELECTED.value

    db.commit()

    return ApiResponse.success(
        ImageSelectResponse(
            campaign_id=campaign_id,
            selected_image_id=asset.id,
            status=campaign.status,
        )
    )
