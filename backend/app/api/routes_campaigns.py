"""
Campaign CRUD 路由（落地方案 §9.2–9.4）。

Agent A 实现：
  POST   /api/campaigns                          创建活动（含项目自动创建）
  GET    /api/campaigns                          列表
  GET    /api/campaigns/{campaign_id}            详情

Agent C 实现：
  POST   /api/campaigns/{campaign_id}/plan/generate
  POST   /api/campaigns/{campaign_id}/plan/approve
"""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.state_machine import CampaignStatus, assert_valid_transition
from app.core.utils import new_id, slugify
from app.db.models import Campaign, GenerationTask, Project, Template
from app.db.session import get_db
from app.schemas.campaigns import (
    CampaignCreate,
    CampaignCreateResponse,
    CampaignListResponse,
    CampaignOut,
    PlanApproveRequest,
    PlanApproveResponse,
    PlanGenerateResponse,
)
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


def _campaign_to_out(c: Campaign) -> CampaignOut:
    """将 ORM 对象转为 CampaignOut，解析 JSON 字段。"""
    return CampaignOut(
        id=c.id,
        project_id=c.project_id,
        template_id=c.template_id,
        name=c.name,
        slug=c.slug,
        status=c.status,
        failed_stage=c.failed_stage,
        error_code=c.error_code,
        error_message=c.error_message,
        brief=json.loads(c.brief_json) if c.brief_json else None,
        structured_plan=json.loads(c.structured_plan_json) if c.structured_plan_json else None,
        approved_plan=json.loads(c.approved_plan_json) if c.approved_plan_json else None,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _get_or_create_project(db: Session, project_name: str) -> Project:
    """按名称查找项目，不存在则创建。"""
    slug = slugify(project_name)
    project = db.query(Project).filter(Project.name == project_name).first()
    if project:
        return project

    # slug 冲突时追加短 ID
    existing_slug = db.query(Project).filter(Project.slug == slug).first()
    if existing_slug:
        slug = f"{slug}_{new_id('')[1:]}"  # strip prefix underscore

    project = Project(
        id=new_id("prj"),
        name=project_name,
        slug=slug,
    )
    db.add(project)
    db.flush()
    return project


# ── POST /api/campaigns ───────────────────────────────────────────────────────

@router.post("", response_model=ApiResponse[CampaignCreateResponse], status_code=201)
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db)):
    """
    创建活动。
    - 若 project_name 对应项目不存在，自动创建。
    - 若 brief 已提供，状态直接设为 brief_ready；否则为 draft。
    """
    project = _get_or_create_project(db, body.project_name)

    # 验证 template_id（若提供）
    if body.template_id:
        from app.db.models import Template
        tpl = db.get(Template, body.template_id)
        if tpl is None:
            raise ValidationError(f"模板 '{body.template_id}' 不存在")

    slug = slugify(body.campaign_name)
    # 同一项目内 slug 冲突时追加短 ID
    existing = (
        db.query(Campaign)
        .filter(Campaign.project_id == project.id, Campaign.slug == slug)
        .first()
    )
    if existing:
        slug = f"{slug}_{new_id('')[1:]}"

    status = CampaignStatus.BRIEF_READY if body.brief else CampaignStatus.DRAFT

    campaign = Campaign(
        id=new_id("cmp"),
        project_id=project.id,
        template_id=body.template_id,
        name=body.campaign_name,
        slug=slug,
        status=status.value,
        brief_json=json.dumps(body.brief, ensure_ascii=False) if body.brief else None,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return ApiResponse.success(
        CampaignCreateResponse(campaign_id=campaign.id, status=campaign.status)
    )


# ── GET /api/campaigns ────────────────────────────────────────────────────────

@router.get("", response_model=ApiResponse[CampaignListResponse])
def list_campaigns(
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Campaign)
    if project_id:
        q = q.filter(Campaign.project_id == project_id)
    if status:
        q = q.filter(Campaign.status == status)
    campaigns = q.order_by(Campaign.created_at.desc()).all()
    items = [_campaign_to_out(c) for c in campaigns]
    return ApiResponse.success(CampaignListResponse(items=items))


# ── GET /api/campaigns/{campaign_id} ─────────────────────────────────────────

@router.get("/{campaign_id}", response_model=ApiResponse[CampaignOut])
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Campaign", campaign_id)
    return ApiResponse.success(_campaign_to_out(campaign))


# ── POST /api/campaigns/{campaign_id}/plan/generate ───────────────────────────

@router.post(
    "/{campaign_id}/plan/generate",
    response_model=ApiResponse[PlanGenerateResponse],
)
async def generate_plan(campaign_id: str, db: Session = Depends(get_db)):
    """
    调用 Brief Agent 将 brief 表单生成结构化视觉方案。

    活动必须处于 brief_ready 状态；若已处于 plan_pending_review，则允许重新生成方案。
    成功后状态推进至 plan_pending_review，等待用户确认。
    """
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Campaign", campaign_id)

    allowed_statuses = {
        CampaignStatus.BRIEF_READY.value,
        CampaignStatus.PLAN_PENDING_REVIEW.value,
    }
    if campaign.status not in allowed_statuses:
        raise ValidationError(
            f"活动状态 '{campaign.status}' 不支持生成方案，需要处于 brief_ready 或 plan_pending_review"
        )

    if not campaign.brief_json:
        raise ValidationError("活动尚未填写 Brief，无法生成方案")

    brief: dict = json.loads(campaign.brief_json)
    template = db.get(Template, campaign.template_id) if campaign.template_id else None

    # 首次生成时推进状态；重新生成时保持 plan_pending_review，避免引入额外接口。
    if campaign.status == CampaignStatus.BRIEF_READY.value:
        assert_valid_transition(campaign.status, CampaignStatus.PLAN_PENDING_REVIEW.value)
        campaign.status = CampaignStatus.PLAN_PENDING_REVIEW.value
    db.flush()

    # 创建 GenerationTask 留痕
    task = GenerationTask(
        id=new_id("gtsk"),
        campaign_id=campaign_id,
        task_type="brief_plan",
        status="running",
        model=settings.ANTHROPIC_MODEL,
        provider="claude",
        input_json=json.dumps({"brief": brief}, ensure_ascii=False),
    )
    db.add(task)
    db.flush()

    # 调用 Brief Agent
    try:
        from app.services.brief_agent import BriefAgent
        agent = BriefAgent()
        structured_plan = await agent.generate_plan(
            brief=brief,
            template_name=template.name if template else None,
            template_description=template.description if template else None,
        )
    except Exception as exc:
        campaign.status = CampaignStatus.FAILED.value
        campaign.failed_stage = "brief_plan"
        campaign.error_message = str(exc)
        task.status = "failed"
        task.error_message = str(exc)
        db.commit()
        raise AppError("PLAN_GENERATION_FAILED", f"方案生成失败：{exc}", status_code=502)

    # 保存结构化方案
    plan_json = json.dumps(structured_plan, ensure_ascii=False)
    campaign.structured_plan_json = plan_json
    task.status = "completed"
    task.output_json = plan_json

    db.commit()

    return ApiResponse.success(
        PlanGenerateResponse(
            campaign_id=campaign_id,
            task_id=task.id,
            status=campaign.status,
            structured_plan=structured_plan,
        )
    )


# ── POST /api/campaigns/{campaign_id}/plan/approve ────────────────────────────

@router.post(
    "/{campaign_id}/plan/approve",
    response_model=ApiResponse[PlanApproveResponse],
)
def approve_plan(
    campaign_id: str,
    body: PlanApproveRequest,
    db: Session = Depends(get_db),
):
    """
    用户确认视觉方案，将 approved_plan 写入活动记录。

    活动必须处于 plan_pending_review 状态。
    成功后状态推进至 plan_approved，等待 Agent B 生成底图。
    """
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Campaign", campaign_id)

    assert_valid_transition(campaign.status, CampaignStatus.PLAN_APPROVED.value)

    campaign.approved_plan_json = json.dumps(body.approved_plan, ensure_ascii=False)
    campaign.status = CampaignStatus.PLAN_APPROVED.value

    db.commit()

    return ApiResponse.success(
        PlanApproveResponse(campaign_id=campaign_id, status=campaign.status)
    )
