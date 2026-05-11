"""
Prompt Agent：将确认后的视觉方案拆成底图 prompt 和 HTML prompt（落地方案 §Agent 设计 / Prompt Agent）。

输入：approved_plan + brief + 尺寸 + 可选模板 prompt 模板
输出：{"image_prompt": str, "html_prompt": str}
"""

import json
import re

from app.services.claude_provider import LlmProvider

_SYSTEM = """\
你是一位专业的 AI 提示词工程师，擅长将营销 brief 与视觉方案转成可直接执行的高质量生成提示词。

任务：根据输入内容生成两个字段：
1) image_prompt（用于图像模型，英文）
2) html_prompt（用于 HTML 生成模型，中文）

image_prompt 要求：
- 必须使用英文。
- 必须体现城市营销场景中的关键信息：城市地标、产业元素、节日情绪（若输入包含）。
- 按以下顺序组织信息：subject / background / foreground / sky and light / composition / color palette / style / negative constraints。
- 明确指定比例（例如 9:16 或 16:9）。
- 构图约束：地标位于中上部，天空留出呼吸空间（可见开阔天空），底部 1/4 预留文字排版空间（clean area reserved for text overlay）。
- 风格约束：明亮、通透、高饱和、商业营销海报质感，避免阴暗压抑。
- negative constraints 至少包含：no text, no words, no letters, no Chinese characters, no watermark, no logo, no people close-up, no dark mood, no collage, no over-filtered look, no cartoonish style。

html_prompt 要求：
- 必须使用中文。
- 明确要求生成完整单文件 HTML（从 <!DOCTYPE html> 开始）。
- 明确要求底图使用 CSS background-image，且 background-size: cover、background-position: center。
- 明确要求样式只能内联或在 <style> 标签中，不引用外部 CSS。
- 明确要求不使用任何 <script> 标签，不使用内联事件处理器（onclick/onload/onerror 等）。
- 明确要求文字层级（节日标识、主标题、正文、落款/客户经理）与可读性处理（底部压暗渐变遮罩或半透明色块）。
- 明确列出必须出现的关键文字字段（从 brief 提取）。

下面是一个合法 JSON one-shot 示例（仅用于学习输出风格与信息密度）：
{
  "image_prompt": "Shenzhen Labor Day marketing poster background, 9:16 vertical aspect ratio. Subject: a bright and uplifting city-industry scene celebrating creators and workers. Background: Shenzhen Bay, Shenzhen Bay Bridge, and a modern skyline with glass office towers under a vivid blue sky. Foreground: subtle technology and software industry cues integrated naturally through modern business park architecture, reflective glass surfaces, and restrained digital accents, without close-up people. Sky and light: sunny morning light, transparent atmosphere, high saturation, energetic holiday mood. Composition: landmarks in the upper and middle area, open sky occupying at least 30 percent of the frame, clean bottom quarter reserved for text overlay, suitable for a premium marketing poster background. Color palette: electric cyan, bright blue, warm sunlight, clean white highlights. Style: bright commercial city photography blended with refined festive visual design, realistic and polished. Negative constraints: no text, no words, no letters, no Chinese characters, no watermark, no logo, no people close-up, no dark mood, no collage, no over-filtered look, no cartoonish style.",
  "html_prompt": "请生成一个完整单文件 HTML 五一劳动节营销海报，从 <!DOCTYPE html> 开始，只输出 HTML 代码。海报为 9:16 竖版，底图必须通过 CSS background-image 引用并使用 background-size: cover、background-position: center。整体风格明亮、专业、克制，有城市科技感和节日祝福氛围。版式要求：上方保留城市与节日氛围，中下部建立清晰文字层级，底部 1/4 使用压暗渐变遮罩或半透明深色信息区，确保文字清晰可读。必须出现以下关键文字：五一劳动节、深圳、这座城市从不问你从哪里来，只看你造了什么、五一，致敬每一个在深圳创造的人、微众银行、谢艾铭。文字层级包括节日标识、主标题、两行正文文案、客户经理落款。所有样式写在 <style> 标签或内联样式中，不引用外部 CSS，不使用任何 <script> 标签，不使用 onclick、onload、onerror 等内联事件处理器。"
}

注意：上面的 JSON 仅为示例。
处理真实输入时，只输出一个 JSON object，且必须且只能包含两个字段：image_prompt 和 html_prompt。
两个字段的值都必须是字符串。
不要输出 markdown，不要输出解释，不要输出示例输入，不要输出多余字段，不要输出数组。\
"""


def _parse_json(raw: str) -> dict:
    """从 Claude 响应中提取 JSON，兼容 markdown 代码块包裹。"""
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    text = m.group(1) if m else raw.strip()
    return json.loads(text)


class PromptAgent:
    def __init__(self, provider: LlmProvider | None = None):
        self.provider = provider or LlmProvider()

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
