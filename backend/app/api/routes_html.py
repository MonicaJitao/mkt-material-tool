"""
HTML 生成、版本管理与预览路由（落地方案 §9.8–9.12）。

Agent C 实现：
  POST   /api/campaigns/{campaign_id}/html/generate   生成 HTML 海报
  GET    /api/campaigns/{campaign_id}/html             列出活动下所有海报
  GET    /api/html/{version_id}                        获取版本内容（JSON）
  GET    /api/html/{version_id}/preview                HTML 沙箱预览
  GET    /api/html/{version_id}/raw                    旧预览地址兼容
  POST   /api/html/{poster_id}/versions                保存手动编辑版本
  GET    /api/html/poster/{poster_id}                  获取海报及版本列表
"""

import base64
import json
import mimetypes
import os
import re

import aiofiles
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.state_machine import CampaignStatus, assert_valid_transition
from app.core.utils import new_id
from app.db.models import Campaign, GenerationTask, HtmlPoster, HtmlVersion, ImageAsset, Project, Template
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.html import (
    HtmlGenerateRequest,
    HtmlGenerateResponse,
    HtmlPosterOut,
    HtmlVersionContent,
    HtmlVersionOut,
    HtmlVersionSaveRequest,
    HtmlVersionSaveResponse,
    ValidationResult,
)
from app.services.claude_provider import ClaudeProvider
from app.services.html_validation import validate_html
from app.services.prompt_agent import PromptAgent

# ── 路由器 ────────────────────────────────────────────────────────────────────

campaigns_router = APIRouter(prefix="/api/campaigns", tags=["html"])
html_router = APIRouter(prefix="/api/html", tags=["html"])

# ── HTML 生成系统提示词 ────────────────────────────────────────────────────────

_HTML_SYSTEM = """\
你是一位专业的 HTML 海报设计师。根据提供的视觉方案、用户 Brief 和底图，生成一个完整的单文件 HTML 海报。

严格要求：
1. 输出完整 HTML 文档，从 <!DOCTYPE html> 开始
2. 所有样式必须内联或在 <style> 标签中，不引用任何外部 CSS 文件
3. 绝对不允许使用任何 <script> 标签（包括外链脚本）
4. 绝对不允许使用内联事件处理器（onclick、onload、onerror 等）
5. 底图必须通过 CSS background-image 引用，background-size: cover，background-position: center
6. 文字区域必须有可读性处理（底部压暗渐变遮罩或半透明色块）
7. 所有关键文字字段（公司名、活动名、客户经理姓名等）必须出现在 HTML 中
8. 海报尺寸使用固定宽高比，宽度 100vw 或固定像素，高度按比例计算

只输出 HTML 代码，不要有任何其他文字、解释或 markdown 标记。\
"""

# ── 内部工具函数 ──────────────────────────────────────────────────────────────

def _extract_html(raw: str) -> str:
    """从 Claude 响应中提取 HTML，兼容 markdown 代码块包裹。"""
    m = re.search(r"```(?:html)?\s*\n(.*?)\n```", raw, re.DOTALL)
    if m:
        return m.group(1).strip()
    stripped = raw.strip()
    return stripped


def _embed_image_base64(html_content: str, image_abs_path: str) -> str:
    """将 HTML 中的底图 URL 替换为 base64 data URI，使 HTML 自包含可分享。"""
    if not os.path.exists(image_abs_path):
        return html_content

    mime_type = mimetypes.guess_type(image_abs_path)[0] or "image/jpeg"

    with open(image_abs_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    data_uri = f"data:{mime_type};base64,{b64}"
    return re.sub(r"url\(['\"]?/workspace/[^'\")\s]+['\"]?\)", f"url('{data_uri}')", html_content)


def _get_required_fields(brief: dict) -> list[str]:
    """从 brief 中提取需要在 HTML 中出现的关键文字字段值。"""
    fields = []
    for key in ("company_name", "manager_name", "festival", "product_name", "activity_name"):
        val = brief.get(key)
        if val and isinstance(val, str):
            fields.append(val)
    return fields


def _build_html_prompt(
    brief: dict,
    approved_plan: dict,
    image_url: str,
    size: str,
    template: Template | None,
) -> str:
    """组装发给 Claude 的 HTML 生成 user message。"""
    parts: list[str] = []

    if approved_plan:
        parts.append(f"视觉方案：\n{json.dumps(approved_plan, ensure_ascii=False, indent=2)}")

    if brief:
        parts.append(f"用户 Brief：\n{json.dumps(brief, ensure_ascii=False, indent=2)}")

    parts.append(f"底图 URL（必须作为背景图引用）：{image_url}")
    parts.append(f"输出尺寸比例：{size}")

    if template and template.html_prompt_template:
        try:
            filled = template.html_prompt_template.format(**brief)
        except (KeyError, ValueError):
            filled = template.html_prompt_template
        parts.append(f"模板补充要求：{filled}")

    return "\n\n".join(parts)


def _html_rel_path(project_slug: str, campaign_slug: str, poster_id: str, version_no: int) -> str:
    """生成符合落地方案 §6 的 HTML 版本路径；poster_id 保留用于兼容既有调用。"""
    return os.path.join("projects", project_slug, campaign_slug, "html", f"poster_v{version_no:03d}.html")


def _html_abs_path(rel_path: str) -> str:
    return os.path.join(settings.WORKSPACE_DIR, rel_path)


def _next_version_no(db: Session, poster_id: str) -> int:
    max_no = (
        db.query(func.max(HtmlVersion.version_no))
        .filter(HtmlVersion.poster_id == poster_id)
        .scalar()
    )
    return (max_no or 0) + 1


def _version_to_out(v: HtmlVersion) -> HtmlVersionOut:
    return HtmlVersionOut(
        id=v.id,
        poster_id=v.poster_id,
        version_no=v.version_no,
        source=v.source,
        html_path=v.html_path,
        model=v.model,
        validation=json.loads(v.validation_json) if v.validation_json else None,
        created_at=v.created_at,
    )


def _poster_to_out(p: HtmlPoster) -> HtmlPosterOut:
    return HtmlPosterOut(
        id=p.id,
        campaign_id=p.campaign_id,
        selected_image_id=p.selected_image_id,
        title=p.title,
        current_version_id=p.current_version_id,
        status=p.status,
        created_at=p.created_at,
        updated_at=p.updated_at,
        versions=[_version_to_out(v) for v in p.versions],
    )


# ── POST /api/campaigns/{campaign_id}/html/generate ───────────────────────────

_HTML_GEN_VALID_STATES = {
    CampaignStatus.IMAGE_SELECTED.value,
    CampaignStatus.HTML_READY.value,
    CampaignStatus.EDITING.value,
    CampaignStatus.FAILED.value,
}


@campaigns_router.post(
    "/{campaign_id}/html/generate",
    response_model=ApiResponse[HtmlGenerateResponse],
    status_code=200,
)
async def generate_html(
    campaign_id: str,
    body: HtmlGenerateRequest,
    db: Session = Depends(get_db),
):
    """
    调用 Claude 生成 HTML 海报。

    流程：
    1. 校验活动状态（image_selected / html_ready / editing / failed）
    2. 加载底图、项目、模板
    3. 用 PromptAgent 生成 html_prompt（若 approved_plan 存在）
    4. 调用 ClaudeProvider 生成 HTML
    5. 校验 HTML 安全性
    6. 保存 HTML 文件（版本化，不覆盖旧版本）
    7. 写入 HtmlPoster / HtmlVersion / GenerationTask 记录
    8. 推进活动状态至 html_ready
    """
    # 1. 加载活动
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Campaign", campaign_id)

    if campaign.status not in _HTML_GEN_VALID_STATES:
        raise ValidationError(
            f"活动状态 '{campaign.status}' 不支持生成 HTML，"
            f"需要处于 {sorted(_HTML_GEN_VALID_STATES)} 之一"
        )

    # 2. 加载底图
    image = db.get(ImageAsset, body.selected_image_id)
    if image is None or image.campaign_id != campaign_id:
        raise NotFoundError("ImageAsset", body.selected_image_id)
    if image.status != "completed" or not image.local_path:
        raise ValidationError("选中的底图尚未完成下载，无法生成 HTML")

    # 3. 加载项目和模板
    project = db.get(Project, campaign.project_id)
    template = db.get(Template, campaign.template_id) if campaign.template_id else None

    # 4. 解析 brief / approved_plan
    brief: dict = json.loads(campaign.brief_json) if campaign.brief_json else {}
    approved_plan: dict = json.loads(campaign.approved_plan_json) if campaign.approved_plan_json else {}

    size: str = brief.get("size") or (template.default_size if template else "9:16")

    # 5. 构建底图 URL（workspace 目录通过静态文件服务暴露）
    image_url = f"/workspace/{image.local_path.replace(os.sep, '/')}"
    image_filename = os.path.basename(image.local_path)

    # 6. 构建 html_prompt
    html_prompt = ""
    if approved_plan:
        try:
            prompt_result = await PromptAgent().generate_prompts(
                approved_plan=approved_plan,
                brief=brief,
                size=size,
                template_image_prompt=template.image_prompt_template if template else None,
                template_html_prompt=template.html_prompt_template if template else None,
            )
            html_prompt = prompt_result.get("html_prompt", "")
        except Exception:
            html_prompt = ""

    if not html_prompt:
        html_prompt = _build_html_prompt(brief, approved_plan, image_url, size, template)
    else:
        html_prompt = "\n\n".join(
            [
                html_prompt,
                f"选中底图 URL（必须作为 CSS background-image 引用）：{image_url}",
                f"选中底图文件名（HTML 中必须出现）：{image_filename}",
                f"输出尺寸比例：{size}",
            ]
        )

    # 7. 推进状态至 html_generating
    assert_valid_transition(campaign.status, CampaignStatus.HTML_GENERATING.value)
    campaign.status = CampaignStatus.HTML_GENERATING.value
    db.flush()

    # 8. 创建 GenerationTask 记录（留痕）
    model_name = body.model or settings.ANTHROPIC_MODEL
    task = GenerationTask(
        id=new_id("gtsk"),
        campaign_id=campaign_id,
        task_type="html_generation",
        status="running",
        model=model_name,
        provider="claude",
        input_json=json.dumps(
            {
                "brief": brief,
                "approved_plan": approved_plan,
                "selected_image_id": body.selected_image_id,
                "size": size,
            },
            ensure_ascii=False,
        ),
        prompt_text=html_prompt,
    )
    db.add(task)
    db.flush()

    # 9. 调用 Claude 生成 HTML
    try:
        provider = ClaudeProvider(model=model_name)
        raw_response = await provider.complete(
            system=_HTML_SYSTEM,
            user_message=html_prompt,
            model=model_name,
        )
        html_content = _extract_html(raw_response)
    except Exception as exc:
        campaign.status = CampaignStatus.FAILED.value
        campaign.failed_stage = "html_generating"
        campaign.error_message = str(exc)
        task.status = "failed"
        task.error_message = str(exc)
        db.commit()
        raise AppError("HTML_GENERATION_FAILED", f"HTML 生成失败：{exc}", status_code=502)

    # 9.5 将底图转为 base64 内嵌，使 HTML 可独立分享
    image_abs_path = os.path.join(settings.WORKSPACE_DIR, image.local_path)
    html_content = _embed_image_base64(html_content, image_abs_path)

    # 10. 校验 HTML
    required_fields = _get_required_fields(brief)
    validation = validate_html(
        html_content,
        image_filename=image_filename,
        required_text_fields=required_fields,
    )

    # 11. 查找或创建 HtmlPoster
    poster = (
        db.query(HtmlPoster)
        .filter(
            HtmlPoster.campaign_id == campaign_id,
            HtmlPoster.selected_image_id == body.selected_image_id,
        )
        .first()
    )
    if poster is None:
        poster = HtmlPoster(
            id=new_id("hpst"),
            campaign_id=campaign_id,
            selected_image_id=body.selected_image_id,
            title=campaign.name,
            status="html_generating",
        )
        db.add(poster)
        db.flush()

    # 12. 确定版本号（递增，不覆盖旧版本）
    version_no = _next_version_no(db, poster.id)

    # 13. 保存 HTML 文件
    rel_path = _html_rel_path(project.slug, campaign.slug, poster.id, version_no)
    abs_path = _html_abs_path(rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    async with aiofiles.open(abs_path, "w", encoding="utf-8") as f:
        await f.write(html_content)

    # 14. 创建 HtmlVersion 记录
    version = HtmlVersion(
        id=new_id("hver"),
        poster_id=poster.id,
        version_no=version_no,
        source="model",
        html_path=rel_path,
        prompt_text=html_prompt,
        model=model_name,
        validation_json=json.dumps(validation.model_dump(), ensure_ascii=False),
    )
    db.add(version)
    db.flush()

    # 15. 更新 HtmlPoster
    poster.current_version_id = version.id
    poster.status = "html_ready"

    # 16. 更新 GenerationTask
    task.status = "completed"
    task.output_json = json.dumps(
        {"poster_id": poster.id, "version_id": version.id, "version_no": version_no},
        ensure_ascii=False,
    )

    # 17. 推进活动状态至 html_ready
    campaign.status = CampaignStatus.HTML_READY.value
    campaign.failed_stage = None
    campaign.error_message = None

    db.commit()

    return ApiResponse.success(
        HtmlGenerateResponse(
            poster_id=poster.id,
            version_id=version.id,
            status="html_ready",
            preview_url=f"/api/html/{version.id}/preview",
            validation=validation,
        )
    )


# ── GET /api/campaigns/{campaign_id}/html ─────────────────────────────────────

@campaigns_router.get(
    "/{campaign_id}/html",
    response_model=ApiResponse[list[HtmlPosterOut]],
)
def list_posters(campaign_id: str, db: Session = Depends(get_db)):
    """列出活动下所有 HTML 海报（含版本列表）。"""
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Campaign", campaign_id)

    posters = (
        db.query(HtmlPoster)
        .filter(HtmlPoster.campaign_id == campaign_id)
        .order_by(HtmlPoster.created_at.desc())
        .all()
    )
    return ApiResponse.success([_poster_to_out(p) for p in posters])


# ── GET /api/html/poster/{poster_id} ─────────────────────────────────────────
# 注意：此路由必须在 /{version_id} 之前注册，避免 "poster" 被当作 version_id

@html_router.get(
    "/poster/{poster_id}",
    response_model=ApiResponse[HtmlPosterOut],
)
def get_poster(poster_id: str, db: Session = Depends(get_db)):
    """获取海报详情及完整版本列表。"""
    poster = db.get(HtmlPoster, poster_id)
    if poster is None:
        raise NotFoundError("HtmlPoster", poster_id)
    return ApiResponse.success(_poster_to_out(poster))


# ── GET /api/html/{version_id} ────────────────────────────────────────────────

@html_router.get(
    "/{version_id}",
    response_model=ApiResponse[HtmlVersionContent],
)
async def get_version_content(version_id: str, db: Session = Depends(get_db)):
    """获取指定版本的 HTML 内容（JSON 格式，含 html 字段）。"""
    version = db.get(HtmlVersion, version_id)
    if version is None:
        raise NotFoundError("HtmlVersion", version_id)

    if not version.html_path:
        raise ValidationError("该版本没有关联的 HTML 文件路径")

    abs_path = _html_abs_path(version.html_path)
    if not os.path.exists(abs_path):
        raise ValidationError(f"HTML 文件不存在：{version.html_path}")

    async with aiofiles.open(abs_path, "r", encoding="utf-8") as f:
        html_content = await f.read()

    return ApiResponse.success(
        HtmlVersionContent(
            version_id=version.id,
            poster_id=version.poster_id,
            version_no=version.version_no,
            source=version.source,
            html=html_content,
            created_at=version.created_at,
        )
    )


# ── GET /api/html/{version_id}/preview ────────────────────────────────────────

async def _version_html_response(version_id: str, db: Session) -> HTMLResponse:
    """
    返回原始 HTML 内容（Content-Type: text/html）。
    前端 iframe 可直接将 src 指向此 URL 实现沙箱预览。
    """
    version = db.get(HtmlVersion, version_id)
    if version is None:
        return HTMLResponse("<h1>版本不存在</h1>", status_code=404)

    if not version.html_path:
        return HTMLResponse("<h1>HTML 文件路径为空</h1>", status_code=404)

    abs_path = _html_abs_path(version.html_path)
    if not os.path.exists(abs_path):
        return HTMLResponse(f"<h1>HTML 文件不存在：{version.html_path}</h1>", status_code=404)

    async with aiofiles.open(abs_path, "r", encoding="utf-8") as f:
        html_content = await f.read()

    return HTMLResponse(content=html_content, status_code=200)


@html_router.get("/{version_id}/preview", response_class=HTMLResponse)
async def get_version_preview(version_id: str, db: Session = Depends(get_db)):
    """契约预览接口：GET /api/html/{version_id}/preview。"""
    return await _version_html_response(version_id, db)


@html_router.get("/{version_id}/raw", response_class=HTMLResponse)
async def get_version_raw(version_id: str, db: Session = Depends(get_db)):
    """兼容旧前端的 raw 预览地址。"""
    return await _version_html_response(version_id, db)


# ── POST /api/html/{poster_id}/versions ──────────────────────────────────────

@html_router.post(
    "/{poster_id}/versions",
    response_model=ApiResponse[HtmlVersionSaveResponse],
    status_code=201,
)
async def save_version(
    poster_id: str,
    body: HtmlVersionSaveRequest,
    db: Session = Depends(get_db),
):
    """
    保存手动编辑后的 HTML 为新版本（不覆盖旧版本）。

    同时将活动状态推进至 html_ready（若当前为 editing）。
    """
    poster = db.get(HtmlPoster, poster_id)
    if poster is None:
        raise NotFoundError("HtmlPoster", poster_id)

    campaign = db.get(Campaign, poster.campaign_id)
    project = db.get(Project, campaign.project_id)

    # 校验 HTML
    validation = validate_html(body.html)

    # 将底图转为 base64 内嵌，使 HTML 可独立分享
    if poster.selected_image_id:
        image = db.get(ImageAsset, poster.selected_image_id)
        if image and image.local_path:
            image_abs_path = os.path.join(settings.WORKSPACE_DIR, image.local_path)
            body_html = _embed_image_base64(body.html, image_abs_path)
        else:
            body_html = body.html
    else:
        body_html = body.html

    # 确定版本号
    version_no = _next_version_no(db, poster_id)

    # 保存文件
    rel_path = _html_rel_path(project.slug, campaign.slug, poster_id, version_no)
    abs_path = _html_abs_path(rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    async with aiofiles.open(abs_path, "w", encoding="utf-8") as f:
        await f.write(body_html)

    # 创建版本记录
    version = HtmlVersion(
        id=new_id("hver"),
        poster_id=poster_id,
        version_no=version_no,
        source=body.source,
        html_path=rel_path,
        validation_json=json.dumps(validation.model_dump(), ensure_ascii=False),
    )
    db.add(version)
    db.flush()

    # 更新 poster
    poster.current_version_id = version.id
    poster.status = "html_ready"

    # 若活动处于 editing 状态，推进至 html_ready
    if campaign.status == CampaignStatus.EDITING.value:
        campaign.status = CampaignStatus.HTML_READY.value

    db.commit()

    return ApiResponse.success(
        HtmlVersionSaveResponse(
            poster_id=poster_id,
            version_id=version.id,
            version_no=version_no,
            validation=validation,
        )
    )
