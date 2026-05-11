"""
HTML 安全校验单元测试（落地方案 §最小 HTML 安全与结构校验）。

覆盖：
- 合法 HTML 通过校验
- <script> 标签被拦截（开标签、闭标签、外链脚本）
- 内联事件处理器被拦截（onclick、onload、onerror 等）
- javascript: URL 被拦截
- 空 HTML 被拦截
- 底图文件名检查
- 必填字段检查
"""

import pytest

from app.services.html_validation import validate_html


# ── 合法 HTML ─────────────────────────────────────────────────────────────────

VALID_HTML = """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="UTF-8"><title>海报</title>
<style>
  body { margin: 0; background-image: url('/workspace/projects/p/c/assets/bg.jpg');
         background-size: cover; }
  .overlay { background: rgba(0,0,0,0.4); padding: 20px; }
</style>
</head>
<body>
  <div class="overlay">
    <h1>微众银行</h1>
    <p>五一劳动节快乐</p>
    <p>客户经理：张三</p>
  </div>
</body>
</html>"""


def test_valid_html_passes():
    result = validate_html(VALID_HTML)
    assert result.ok is True
    assert result.issues == []


# ── <script> 拦截 ─────────────────────────────────────────────────────────────

def test_script_open_tag_blocked():
    html = VALID_HTML.replace("</style>", "</style><script>alert(1)</script>")
    result = validate_html(html)
    assert result.ok is False
    assert any("<script>" in issue for issue in result.issues)


def test_script_close_tag_alone_blocked():
    html = VALID_HTML + "</script>"
    result = validate_html(html)
    assert result.ok is False


def test_external_script_blocked():
    html = VALID_HTML.replace("</head>", '<script src="https://evil.com/x.js"></script></head>')
    result = validate_html(html)
    assert result.ok is False
    assert any("<script>" in issue for issue in result.issues)


def test_script_tag_case_insensitive():
    html = VALID_HTML + "<SCRIPT>alert(1)</SCRIPT>"
    result = validate_html(html)
    assert result.ok is False


def test_script_tag_with_spaces():
    html = VALID_HTML + "< script >alert(1)</ script >"
    result = validate_html(html)
    assert result.ok is False


# ── 内联事件处理器拦截 ────────────────────────────────────────────────────────

def test_onclick_blocked():
    html = VALID_HTML.replace("<h1>微众银行</h1>", '<h1 onclick="alert(1)">微众银行</h1>')
    result = validate_html(html)
    assert result.ok is False
    assert any("事件处理器" in issue for issue in result.issues)


def test_onload_blocked():
    html = VALID_HTML.replace("<body>", '<body onload="init()">')
    result = validate_html(html)
    assert result.ok is False


def test_onerror_blocked():
    html = VALID_HTML.replace("<body>", '<body onerror="x()">')
    result = validate_html(html)
    assert result.ok is False


def test_event_handler_case_insensitive():
    html = VALID_HTML.replace("<body>", '<body ONCLICK="x()">')
    result = validate_html(html)
    assert result.ok is False


# ── javascript: URL 拦截 ──────────────────────────────────────────────────────

def test_javascript_href_blocked():
    html = VALID_HTML.replace("<h1>微众银行</h1>", '<a href="javascript:alert(1)">微众银行</a>')
    result = validate_html(html)
    assert result.ok is False
    assert any("javascript:" in issue for issue in result.issues)


def test_javascript_url_with_spaces_blocked():
    html = VALID_HTML.replace("<h1>微众银行</h1>", '<a href="javascript : alert(1)">x</a>')
    result = validate_html(html)
    assert result.ok is False


# ── 空 HTML 拦截 ──────────────────────────────────────────────────────────────

def test_empty_html_blocked():
    result = validate_html("")
    assert result.ok is False
    assert any("为空" in issue for issue in result.issues)


def test_whitespace_only_html_blocked():
    result = validate_html("   \n\t  ")
    assert result.ok is False


# ── 底图文件名检查 ─────────────────────────────────────────────────────────────

def test_image_filename_present_passes():
    result = validate_html(VALID_HTML, image_filename="bg.jpg")
    assert result.ok is True


def test_image_filename_missing_fails():
    result = validate_html(VALID_HTML, image_filename="other_image.jpg")
    assert result.ok is False
    assert any("底图" in issue for issue in result.issues)


def test_image_filename_none_skips_check():
    result = validate_html(VALID_HTML, image_filename=None)
    assert result.ok is True


# ── 必填字段检查 ──────────────────────────────────────────────────────────────

def test_required_fields_present_passes():
    result = validate_html(VALID_HTML, required_text_fields=["微众银行", "张三"])
    assert result.ok is True


def test_required_field_missing_fails():
    result = validate_html(VALID_HTML, required_text_fields=["微众银行", "李四"])
    assert result.ok is False
    assert any("李四" in issue for issue in result.issues)


def test_required_fields_empty_list_passes():
    result = validate_html(VALID_HTML, required_text_fields=[])
    assert result.ok is True


def test_required_fields_none_skips_check():
    result = validate_html(VALID_HTML, required_text_fields=None)
    assert result.ok is True


# ── 多个问题同时报告 ──────────────────────────────────────────────────────────

def test_multiple_issues_all_reported():
    html = '<div onclick="x()"><script>alert(1)</script></div>'
    result = validate_html(html)
    assert result.ok is False
    assert len(result.issues) >= 2


# ── 编辑态 /workspace/... 路径回归验证 ───────────────────────────────────────

def test_workspace_url_reference_passes():
    """编辑态 HTML 保留 /workspace/... 路径，校验器不应误报。"""
    result = validate_html(VALID_HTML, image_filename="bg.jpg")
    assert result.ok is True
    assert result.issues == []


def test_workspace_url_without_base64_passes():
    """不含 base64 data URI 的 /workspace/... 引用应通过校验。"""
    html = VALID_HTML.replace(
        "url('/workspace/projects/p/c/assets/bg.jpg')",
        "url('/workspace/projects/p/c/assets/bg.jpg')",
    )
    result = validate_html(html)
    assert result.ok is True
