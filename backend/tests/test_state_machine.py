"""
状态机单元测试（落地方案 §12.1）。

覆盖：
- 所有合法流转
- 非法流转应抛出 InvalidTransitionError
- failed 态的重试入口
"""

import pytest

from app.core.state_machine import (
    CampaignStatus,
    assert_valid_transition,
    is_valid_transition,
)
from app.core.errors import InvalidTransitionError


# ── 合法流转 ──────────────────────────────────────────────────────────────────

VALID_PATHS = [
    # 主流程
    (CampaignStatus.DRAFT, CampaignStatus.BRIEF_READY),
    (CampaignStatus.BRIEF_READY, CampaignStatus.PLAN_PENDING_REVIEW),
    (CampaignStatus.PLAN_PENDING_REVIEW, CampaignStatus.PLAN_APPROVED),
    (CampaignStatus.PLAN_APPROVED, CampaignStatus.IMAGE_GENERATING),
    (CampaignStatus.IMAGE_GENERATING, CampaignStatus.IMAGE_PENDING_SELECTION),
    (CampaignStatus.IMAGE_PENDING_SELECTION, CampaignStatus.IMAGE_SELECTED),
    (CampaignStatus.IMAGE_SELECTED, CampaignStatus.HTML_GENERATING),
    (CampaignStatus.HTML_GENERATING, CampaignStatus.HTML_READY),
    (CampaignStatus.HTML_READY, CampaignStatus.EDITING),
    (CampaignStatus.EDITING, CampaignStatus.HTML_READY),
    (CampaignStatus.HTML_READY, CampaignStatus.ARCHIVED),
    # 重新生成入口
    (CampaignStatus.PLAN_PENDING_REVIEW, CampaignStatus.BRIEF_READY),
    (CampaignStatus.IMAGE_PENDING_SELECTION, CampaignStatus.IMAGE_GENERATING),
    (CampaignStatus.HTML_READY, CampaignStatus.HTML_GENERATING),
    (CampaignStatus.EDITING, CampaignStatus.HTML_GENERATING),
    # 失败态
    (CampaignStatus.IMAGE_GENERATING, CampaignStatus.FAILED),
    (CampaignStatus.HTML_GENERATING, CampaignStatus.FAILED),
    # 失败重试
    (CampaignStatus.FAILED, CampaignStatus.BRIEF_READY),
    (CampaignStatus.FAILED, CampaignStatus.IMAGE_GENERATING),
    (CampaignStatus.FAILED, CampaignStatus.HTML_GENERATING),
]


@pytest.mark.parametrize("current,target", VALID_PATHS)
def test_valid_transition(current, target):
    assert is_valid_transition(current.value, target.value) is True


@pytest.mark.parametrize("current,target", VALID_PATHS)
def test_assert_valid_transition_does_not_raise(current, target):
    assert_valid_transition(current.value, target.value)  # should not raise


# ── 非法流转 ──────────────────────────────────────────────────────────────────

INVALID_PATHS = [
    # 跳步
    (CampaignStatus.DRAFT, CampaignStatus.PLAN_APPROVED),
    (CampaignStatus.BRIEF_READY, CampaignStatus.IMAGE_GENERATING),
    (CampaignStatus.PLAN_APPROVED, CampaignStatus.HTML_GENERATING),
    # 逆向（非重新生成入口）
    (CampaignStatus.IMAGE_SELECTED, CampaignStatus.PLAN_APPROVED),
    (CampaignStatus.HTML_READY, CampaignStatus.IMAGE_SELECTED),
    # 终态不可流转
    (CampaignStatus.ARCHIVED, CampaignStatus.DRAFT),
    (CampaignStatus.ARCHIVED, CampaignStatus.EDITING),
]


@pytest.mark.parametrize("current,target", INVALID_PATHS)
def test_invalid_transition(current, target):
    assert is_valid_transition(current.value, target.value) is False


@pytest.mark.parametrize("current,target", INVALID_PATHS)
def test_assert_invalid_transition_raises(current, target):
    with pytest.raises(InvalidTransitionError):
        assert_valid_transition(current.value, target.value)


# ── 未知状态 ──────────────────────────────────────────────────────────────────

def test_unknown_status_returns_false():
    assert is_valid_transition("unknown_state", "draft") is False
    assert is_valid_transition("draft", "unknown_state") is False


def test_unknown_status_raises():
    with pytest.raises(InvalidTransitionError):
        assert_valid_transition("unknown_state", "draft")
