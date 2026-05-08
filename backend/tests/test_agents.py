"""
Brief Agent 与 Prompt Agent 单元测试。

使用 AsyncMock patch ClaudeProvider.complete，完全离线运行。

覆盖：
- BriefAgent 正常解析裸 JSON 响应
- BriefAgent 正常解析 markdown 代码块包裹的 JSON
- BriefAgent 传入模板信息时 user_message 包含模板字段
- BriefAgent Claude 返回非法 JSON 时抛出 json.JSONDecodeError
- PromptAgent 正常解析，返回 image_prompt 和 html_prompt
- PromptAgent 传入模板 prompt 参考时 user_message 包含参考内容
- PromptAgent Claude 返回非法 JSON 时抛出异常
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.brief_agent import BriefAgent
from app.services.prompt_agent import PromptAgent

# ── 测试数据 ──────────────────────────────────────────────────────────────────

SAMPLE_BRIEF = {
    "festival": "五一劳动节",
    "audience": "城市企业主",
    "company_name": "微众银行",
    "manager_name": "张三",
    "visual_style": "明亮摄影融合风格",
    "size": "9:16",
}

SAMPLE_PLAN = {
    "campaignTheme": "造城者",
    "audienceInsight": "企业主希望被看见其行业价值",
    "visualStyle": "明亮摄影融合风格",
    "cityLogic": None,
    "copyTone": "克制、真诚、有行业认同感",
    "layoutRules": {
        "textArea": "底部 1/4",
        "titlePosition": "右下或下沿",
        "readability": "底部压暗或半透明色块",
    },
    "keyMessages": ["劳动创造价值", "微众银行与您同行"],
    "colorPalette": "暖金色 + 深蓝",
    "imageDirection": "城市地标与劳动者剪影，暖金色调，底部留白",
}

SAMPLE_PROMPTS = {
    "image_prompt": (
        "City landmark with worker silhouettes, warm golden tones, "
        "no text, no words, aspect ratio 9:16, bottom area reserved for text overlay"
    ),
    "html_prompt": (
        "根据视觉方案生成单文件 HTML 海报，尺寸 9:16，底部 1/4 文字区域，"
        "底部压暗渐变遮罩，包含公司名微众银行、客户经理张三"
    ),
}


# ── BriefAgent 测试 ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_brief_agent_parses_bare_json():
    """BriefAgent 能正确解析 Claude 返回的裸 JSON 字符串。"""
    raw_response = json.dumps(SAMPLE_PLAN, ensure_ascii=False)

    with patch(
        "app.services.brief_agent.ClaudeProvider.complete",
        new_callable=AsyncMock,
        return_value=raw_response,
    ):
        agent = BriefAgent()
        result = await agent.generate_plan(brief=SAMPLE_BRIEF)

    assert result["campaignTheme"] == "造城者"
    assert result["audienceInsight"] == "企业主希望被看见其行业价值"
    assert "layoutRules" in result


@pytest.mark.asyncio
async def test_brief_agent_parses_markdown_wrapped_json():
    """BriefAgent 能正确解析 markdown 代码块包裹的 JSON（Claude 有时会这样输出）。"""
    raw_response = (
        "```json\n"
        + json.dumps(SAMPLE_PLAN, ensure_ascii=False)
        + "\n```"
    )

    with patch(
        "app.services.brief_agent.ClaudeProvider.complete",
        new_callable=AsyncMock,
        return_value=raw_response,
    ):
        agent = BriefAgent()
        result = await agent.generate_plan(brief=SAMPLE_BRIEF)

    assert result["campaignTheme"] == "造城者"


@pytest.mark.asyncio
async def test_brief_agent_includes_template_info_in_message():
    """传入模板信息时，BriefAgent 的 user_message 应包含模板名称和描述。"""
    raw_response = json.dumps(SAMPLE_PLAN, ensure_ascii=False)
    captured_messages: list[str] = []

    async def mock_complete(system, user_message, **kwargs):
        captured_messages.append(user_message)
        return raw_response

    with patch(
        "app.services.brief_agent.ClaudeProvider.complete",
        side_effect=mock_complete,
    ):
        agent = BriefAgent()
        await agent.generate_plan(
            brief=SAMPLE_BRIEF,
            template_name="节日祝福海报",
            template_description="适合五一、端午等节日节点",
        )

    assert len(captured_messages) == 1
    msg = captured_messages[0]
    assert "节日祝福海报" in msg
    assert "适合五一、端午等节日节点" in msg


@pytest.mark.asyncio
async def test_brief_agent_raises_on_invalid_json():
    """Claude 返回非法 JSON 时，BriefAgent 应抛出 json.JSONDecodeError。"""
    with patch(
        "app.services.brief_agent.ClaudeProvider.complete",
        new_callable=AsyncMock,
        return_value="这不是 JSON",
    ):
        agent = BriefAgent()
        with pytest.raises(Exception):
            await agent.generate_plan(brief=SAMPLE_BRIEF)


@pytest.mark.asyncio
async def test_brief_agent_without_template():
    """不传模板信息时，BriefAgent 也能正常工作。"""
    raw_response = json.dumps(SAMPLE_PLAN, ensure_ascii=False)

    with patch(
        "app.services.brief_agent.ClaudeProvider.complete",
        new_callable=AsyncMock,
        return_value=raw_response,
    ):
        agent = BriefAgent()
        result = await agent.generate_plan(brief=SAMPLE_BRIEF)

    assert isinstance(result, dict)
    assert "campaignTheme" in result


# ── PromptAgent 测试 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prompt_agent_returns_both_prompts():
    """PromptAgent 应返回包含 image_prompt 和 html_prompt 的 dict。"""
    raw_response = json.dumps(SAMPLE_PROMPTS, ensure_ascii=False)

    with patch(
        "app.services.prompt_agent.ClaudeProvider.complete",
        new_callable=AsyncMock,
        return_value=raw_response,
    ):
        agent = PromptAgent()
        result = await agent.generate_prompts(
            approved_plan=SAMPLE_PLAN,
            brief=SAMPLE_BRIEF,
            size="9:16",
        )

    assert "image_prompt" in result
    assert "html_prompt" in result
    assert "9:16" in result["image_prompt"] or "9:16" in result["html_prompt"]


@pytest.mark.asyncio
async def test_prompt_agent_parses_markdown_wrapped_json():
    """PromptAgent 能正确解析 markdown 代码块包裹的 JSON。"""
    raw_response = (
        "```json\n"
        + json.dumps(SAMPLE_PROMPTS, ensure_ascii=False)
        + "\n```"
    )

    with patch(
        "app.services.prompt_agent.ClaudeProvider.complete",
        new_callable=AsyncMock,
        return_value=raw_response,
    ):
        agent = PromptAgent()
        result = await agent.generate_prompts(
            approved_plan=SAMPLE_PLAN,
            brief=SAMPLE_BRIEF,
        )

    assert "image_prompt" in result
    assert "html_prompt" in result


@pytest.mark.asyncio
async def test_prompt_agent_includes_template_prompts_in_message():
    """传入模板 prompt 参考时，user_message 应包含参考内容。"""
    raw_response = json.dumps(SAMPLE_PROMPTS, ensure_ascii=False)
    captured_messages: list[str] = []

    async def mock_complete(system, user_message, **kwargs):
        captured_messages.append(user_message)
        return raw_response

    with patch(
        "app.services.prompt_agent.ClaudeProvider.complete",
        side_effect=mock_complete,
    ):
        agent = PromptAgent()
        await agent.generate_prompts(
            approved_plan=SAMPLE_PLAN,
            brief=SAMPLE_BRIEF,
            size="16:9",
            template_image_prompt="节日氛围底图，{festival}，无文字",
            template_html_prompt="生成节日海报，公司：{company_name}",
        )

    assert len(captured_messages) == 1
    msg = captured_messages[0]
    assert "节日氛围底图" in msg
    assert "生成节日海报" in msg
    assert "16:9" in msg


@pytest.mark.asyncio
async def test_prompt_agent_raises_on_invalid_json():
    """Claude 返回非法 JSON 时，PromptAgent 应抛出异常。"""
    with patch(
        "app.services.prompt_agent.ClaudeProvider.complete",
        new_callable=AsyncMock,
        return_value="不是 JSON 内容",
    ):
        agent = PromptAgent()
        with pytest.raises(Exception):
            await agent.generate_prompts(
                approved_plan=SAMPLE_PLAN,
                brief=SAMPLE_BRIEF,
            )


@pytest.mark.asyncio
async def test_prompt_agent_size_passed_to_message():
    """size 参数应出现在发给 Claude 的 user_message 中。"""
    raw_response = json.dumps(SAMPLE_PROMPTS, ensure_ascii=False)
    captured_messages: list[str] = []

    async def mock_complete(system, user_message, **kwargs):
        captured_messages.append(user_message)
        return raw_response

    with patch(
        "app.services.prompt_agent.ClaudeProvider.complete",
        side_effect=mock_complete,
    ):
        agent = PromptAgent()
        await agent.generate_prompts(
            approved_plan=SAMPLE_PLAN,
            brief=SAMPLE_BRIEF,
            size="1:1",
        )

    assert "1:1" in captured_messages[0]
