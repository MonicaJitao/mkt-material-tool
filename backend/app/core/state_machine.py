"""
Campaign 状态机。

合法状态流转图（落地方案 §4）：

  draft
  -> brief_ready
  -> plan_pending_review
  -> plan_approved
  -> image_generating
  -> image_pending_selection
  -> image_selected
  -> html_generating
  -> html_ready
  -> editing
  -> archived

失败态：failed（任意阶段均可进入，记录 failed_stage）
重新生成入口：
  plan_pending_review  -> brief_ready（重新生成方案）
  image_pending_selection -> image_generating（重新生成底图批次）
  html_ready / editing -> html_generating（重新生成 HTML）
"""

from enum import Enum


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    BRIEF_READY = "brief_ready"
    PLAN_PENDING_REVIEW = "plan_pending_review"
    PLAN_APPROVED = "plan_approved"
    IMAGE_GENERATING = "image_generating"
    IMAGE_PENDING_SELECTION = "image_pending_selection"
    IMAGE_SELECTED = "image_selected"
    HTML_GENERATING = "html_generating"
    HTML_READY = "html_ready"
    EDITING = "editing"
    ARCHIVED = "archived"
    FAILED = "failed"


# 每个状态允许流转到的目标状态集合
VALID_TRANSITIONS: dict[CampaignStatus, list[CampaignStatus]] = {
    CampaignStatus.DRAFT: [CampaignStatus.BRIEF_READY],
    CampaignStatus.BRIEF_READY: [CampaignStatus.PLAN_PENDING_REVIEW],
    CampaignStatus.PLAN_PENDING_REVIEW: [
        CampaignStatus.PLAN_APPROVED,
        CampaignStatus.BRIEF_READY,       # 重新生成方案
    ],
    CampaignStatus.PLAN_APPROVED: [CampaignStatus.IMAGE_GENERATING],
    CampaignStatus.IMAGE_GENERATING: [
        CampaignStatus.IMAGE_PENDING_SELECTION,
        CampaignStatus.FAILED,
    ],
    CampaignStatus.IMAGE_PENDING_SELECTION: [
        CampaignStatus.IMAGE_SELECTED,
        CampaignStatus.IMAGE_GENERATING,  # 重新生成底图批次
    ],
    CampaignStatus.IMAGE_SELECTED: [CampaignStatus.HTML_GENERATING],
    CampaignStatus.HTML_GENERATING: [
        CampaignStatus.HTML_READY,
        CampaignStatus.FAILED,
    ],
    CampaignStatus.HTML_READY: [
        CampaignStatus.EDITING,
        CampaignStatus.HTML_GENERATING,   # 基于同一底图重新生成 HTML
        CampaignStatus.ARCHIVED,
    ],
    CampaignStatus.EDITING: [
        CampaignStatus.HTML_READY,        # 保存新版本后回到 html_ready
        CampaignStatus.HTML_GENERATING,   # 重新生成 HTML
        CampaignStatus.ARCHIVED,
    ],
    CampaignStatus.ARCHIVED: [],
    # failed 可从失败阶段重试
    CampaignStatus.FAILED: [
        CampaignStatus.BRIEF_READY,
        CampaignStatus.IMAGE_GENERATING,
        CampaignStatus.HTML_GENERATING,
    ],
}


def is_valid_transition(current: str, target: str) -> bool:
    """检查从 current 到 target 的状态流转是否合法。"""
    try:
        c = CampaignStatus(current)
        t = CampaignStatus(target)
    except ValueError:
        return False
    return t in VALID_TRANSITIONS.get(c, [])


def assert_valid_transition(current: str, target: str) -> None:
    """合法则通过，非法则抛出 InvalidTransitionError。"""
    from app.core.errors import InvalidTransitionError

    if not is_valid_transition(current, target):
        raise InvalidTransitionError(current, target)
