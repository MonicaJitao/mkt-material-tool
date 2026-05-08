"""
最小 HTML 安全校验（落地方案 §最小 HTML 安全与结构校验）。

MVP 校验范围：
1. 不允许 <script> 标签（含外链脚本）
2. 不允许内联事件处理器（onclick、onload 等）
3. 不允许 javascript: URL
4. HTML 不能为空
5. 可选：检查底图文件名是否被引用
6. 可选：检查必填文字字段是否出现在 HTML 中
"""

import re

from app.schemas.html import ValidationResult

# ── 危险内容正则 ──────────────────────────────────────────────────────────────

# <script 或 </script>（含各种空白变体）
_SCRIPT_OPEN = re.compile(r"<\s*script[\s>/]", re.IGNORECASE)
_SCRIPT_CLOSE = re.compile(r"<\s*/\s*script\s*>", re.IGNORECASE)

# 内联事件处理器：空白后跟 on + 字母 + =（例如 onclick=、 onload=）
_INLINE_EVENT = re.compile(r"[\s\"']on[a-z]+\s*=", re.IGNORECASE)

# javascript: URL（href、src、action 等属性中）
_JAVASCRIPT_URL = re.compile(r"javascript\s*:", re.IGNORECASE)


def validate_html(
    html: str,
    image_filename: str | None = None,
    required_text_fields: list[str] | None = None,
) -> ValidationResult:
    """
    对 HTML 字符串执行最小安全校验。

    Args:
        html: 待校验的 HTML 字符串。
        image_filename: 选中底图的文件名（可选）；若提供则检查 HTML 是否引用了该文件。
        required_text_fields: 必须出现在 HTML 文本中的字段值列表（可选）。

    Returns:
        ValidationResult(ok=True/False, issues=[...])
    """
    issues: list[str] = []

    if not html or not html.strip():
        return ValidationResult(ok=False, issues=["HTML 内容为空"])

    if _SCRIPT_OPEN.search(html) or _SCRIPT_CLOSE.search(html):
        issues.append("不允许使用 <script> 标签（含外链脚本）")

    if _INLINE_EVENT.search(html):
        issues.append("不允许使用内联事件处理器（如 onclick、onload 等）")

    if _JAVASCRIPT_URL.search(html):
        issues.append("不允许使用 javascript: URL")

    if image_filename and image_filename not in html:
        issues.append(f"HTML 未引用选中的底图文件（{image_filename}）")

    if required_text_fields:
        for field in required_text_fields:
            if field and field not in html:
                issues.append(f"HTML 缺少必填字段内容：{field}")

    return ValidationResult(ok=len(issues) == 0, issues=issues)
