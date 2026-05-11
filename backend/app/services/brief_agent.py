"""
Brief Agent：将用户填写的表单润色为结构化视觉方案（落地方案 §Agent 设计 / Brief Agent）。

输入：用户 brief 表单 dict + 可选模板信息
输出：结构化视觉方案 JSON dict
"""

import json
import re

from app.services.claude_provider import LlmProvider

_SYSTEM = """\
你是一位专业的营销视觉方案策划师，擅长将简单的营销需求转化为完整的视觉方案。

将用户填写的营销 Brief 表单整理为结构化视觉方案 JSON，字段说明：
- campaignTheme: 活动主题（简洁有力的主题词，5字以内）
- audienceInsight: 目标受众洞察（一句话描述受众核心诉求）
- visualStyle: 视觉风格描述（摄影/插画/渐变等，含色调方向）
- cityLogic: 城市/场景逻辑（地标与产业/节日元素的融合方式；无城市需求时填 null）
- copyTone: 文案语气（例如：克制、真诚、有行业认同感）
- layoutRules: 版式规则，包含子字段：
  - textArea: 文字区域位置（例如：底部 1/4）
  - titlePosition: 标题位置（例如：右下或下沿）
  - readability: 可读性处理方式（例如：底部压暗或半透明色块）
- keyMessages: 核心信息点列表（3-5条字符串）
- colorPalette: 建议色调描述（例如：暖金色 + 深蓝）
- imageDirection: 底图方向建议（描述画面内容和构图，用于指导底图生成）

只输出 JSON，不要有任何其他文字。\
"""


def _parse_json(raw: str) -> dict:
    """从 Claude 响应中提取 JSON，兼容 markdown 代码块包裹。"""
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    text = m.group(1) if m else raw.strip()
    return json.loads(text)


class BriefAgent:
    def __init__(self, provider: LlmProvider  | None = None):
        self.provider = provider or LlmProvider()

    async def generate_plan(
        self,
        brief: dict,
        template_name: str | None = None,
        template_description: str | None = None,
    ) -> dict:
        """
        将 brief 表单生成结构化视觉方案 JSON。

        Args:
            brief: 用户填写的表单字段 dict。
            template_name: 活动模板名称（可选，提供上下文）。
            template_description: 活动模板描述（可选）。

        Returns:
            结构化视觉方案 dict，字段见 _SYSTEM 中的说明。
        """
        parts = [
            f"用户填写的 Brief 表单：\n{json.dumps(brief, ensure_ascii=False, indent=2)}"
        ]
        if template_name:
            parts.append(f"活动模板：{template_name}")
        if template_description:
            parts.append(f"模板说明：{template_description}")

        raw = await self.provider.complete(
            system=_SYSTEM,
            user_message="\n\n".join(parts),
        )
        return _parse_json(raw)
