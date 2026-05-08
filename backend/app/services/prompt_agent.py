"""
Prompt Agent：将确认后的视觉方案拆成底图 prompt 和 HTML prompt（落地方案 §Agent 设计 / Prompt Agent）。

输入：approved_plan + brief + 尺寸 + 可选模板 prompt 模板
输出：{"image_prompt": str, "html_prompt": str}
"""

import json
import re

from app.services.claude_provider import ClaudeProvider

_SYSTEM = """\
你是一位专业的 AI 提示词工程师，擅长为图像生成和 HTML 海报生成编写高质量提示词。

根据确认后的视觉方案，生成两个提示词：

image_prompt（用于 Gemini 图像生成模型）：
- 使用英文
- 描述画面内容、构图、风格、色调、光线
- 明确指定比例（例如 aspect ratio 9:16 或 16:9）
- 必须包含：no text, no words, no letters, no watermark, no people close-up
- 画面留有底部文字排版空间（bottom area reserved for text overlay）
- 适合作为营销海报背景

html_prompt（用于 Claude 生成 HTML 海报）：
- 使用中文
- 描述版式结构、文字层级、颜色方案
- 指定底图使用方式（CSS background-image，object-fit: cover）
- 指定尺寸要求（宽高比，例如 9:16 竖版）
- 要求生成完整单文件 HTML（从 <!DOCTYPE html> 开始）
- 要求所有样式内联或在 <style> 标签中，不引用外部 CSS 文件
- 要求不使用任何 <script> 标签，不使用内联事件处理器
- 要求文字区域有可读性处理（压暗遮罩或半透明色块）
- 列出必须出现在 HTML 中的关键文字字段

只输出 JSON，包含 image_prompt 和 html_prompt 两个字段，不要有任何其他文字。\
"""


def _parse_json(raw: str) -> dict:
    """从 Claude 响应中提取 JSON，兼容 markdown 代码块包裹。"""
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    text = m.group(1) if m else raw.strip()
    return json.loads(text)


class PromptAgent:
    def __init__(self, provider: ClaudeProvider | None = None):
        self.provider = provider or ClaudeProvider()

    async def generate_prompts(
        self,
        approved_plan: dict,
        brief: dict,
        size: str = "9:16",
        template_image_prompt: str | None = None,
        template_html_prompt: str | None = None,
    ) -> dict:
        """
        生成底图 prompt 和 HTML prompt。

        Args:
            approved_plan: 用户确认后的视觉方案 dict。
            brief: 用户原始 brief 表单 dict。
            size: 输出尺寸比例，例如 "9:16" 或 "16:9"。
            template_image_prompt: 模板预设的底图 prompt 参考（可选）。
            template_html_prompt: 模板预设的 HTML prompt 参考（可选）。

        Returns:
            {"image_prompt": str, "html_prompt": str}
        """
        parts = [
            f"视觉方案：\n{json.dumps(approved_plan, ensure_ascii=False, indent=2)}",
            f"用户 Brief：\n{json.dumps(brief, ensure_ascii=False, indent=2)}",
            f"输出尺寸：{size}",
        ]
        if template_image_prompt:
            parts.append(f"底图 prompt 参考模板：{template_image_prompt}")
        if template_html_prompt:
            parts.append(f"HTML prompt 参考模板：{template_html_prompt}")

        raw = await self.provider.complete(
            system=_SYSTEM,
            user_message="\n\n".join(parts),
        )
        return _parse_json(raw)
