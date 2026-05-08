"""ID 与 slug 生成工具。"""

import re
import uuid


def new_id(prefix: str) -> str:
    """生成带前缀的短 UUID，例如 cmp_a1b2c3d4。"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def slugify(text: str) -> str:
    """
    将任意字符串转为 URL/文件系统安全的 slug。
    中文字符保留（SQLite 和文件系统均支持 UTF-8），
    只去除路径分隔符和控制字符，空格转下划线。
    """
    # 去除路径分隔符和常见危险字符
    text = re.sub(r'[/\\:*?"<>|]', "", text)
    # 连续空白转单个下划线
    text = re.sub(r"\s+", "_", text.strip())
    # 去除首尾下划线
    text = text.strip("_")
    if not text:
        return uuid.uuid4().hex[:8]
    return text
