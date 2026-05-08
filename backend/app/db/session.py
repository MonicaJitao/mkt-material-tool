"""
数据库 session 管理与初始化。

启动时调用 init_db() 完成：
  1. 创建 workspace/ 目录
  2. 建表（CREATE TABLE IF NOT EXISTS）
  3. 写入内置模板（幂等）
"""

import json
import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base, Template


def _configure_sqlite(dbapi_conn, _connection_record):
    """开启 WAL 模式，提升 SQLite 并发读写性能。"""
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=settings.DEBUG,
)

# 仅对 SQLite 注册 PRAGMA 钩子
if settings.DATABASE_URL.startswith("sqlite"):
    event.listen(engine, "connect", _configure_sqlite)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：提供请求级 DB session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── 内置模板 ──────────────────────────────────────────────────────────────────

_BUILTIN_TEMPLATES: list[dict] = [
    {
        "id": "festival_poster",
        "name": "节日祝福海报",
        "description": "适合五一、端午、中秋、春节等节日节点",
        "category": "festival",
        "default_size": "9:16",
        "default_image_count": 4,
        "brief_schema_json": json.dumps(
            {
                "fields": [
                    {"key": "festival", "label": "节日/营销节点", "required": True},
                    {"key": "audience", "label": "目标客群", "required": True},
                    {"key": "theme_hint", "label": "主题关键词", "required": False},
                    {"key": "cities", "label": "城市", "required": False, "type": "list"},
                    {"key": "manager_name", "label": "客户经理姓名", "required": False},
                    {"key": "company_name", "label": "公司名称", "required": True},
                    {"key": "visual_style", "label": "视觉风格", "required": False},
                    {"key": "size", "label": "输出尺寸", "required": True, "default": "9:16"},
                ]
            },
            ensure_ascii=False,
        ),
        "image_prompt_template": (
            "节日氛围底图，{festival}，{visual_style}，城市地标与节日元素自然融合，"
            "无文字，无人物特写，适合作为海报背景，比例 {size}"
        ),
        "html_prompt_template": (
            "根据视觉方案和选中底图，生成单文件 HTML 节日祝福海报。"
            "节日：{festival}，公司：{company_name}，客户经理：{manager_name}，"
            "尺寸：{size}，文字区域在底部 1/4，底部压暗处理保证可读性。"
        ),
    },
    {
        "id": "city_industry_poster",
        "name": "城市产业海报",
        "description": "适合城市产业推广、企业主客群营销",
        "category": "city_industry",
        "default_size": "16:9",
        "default_image_count": 4,
        "brief_schema_json": json.dumps(
            {
                "fields": [
                    {"key": "cities", "label": "城市", "required": True, "type": "list"},
                    {"key": "industry", "label": "行业", "required": True},
                    {"key": "audience", "label": "目标客群", "required": True},
                    {"key": "theme_hint", "label": "主题关键词", "required": False},
                    {"key": "manager_name", "label": "客户经理姓名", "required": False},
                    {"key": "company_name", "label": "公司名称", "required": True},
                    {"key": "visual_style", "label": "视觉风格", "required": False},
                    {"key": "size", "label": "输出尺寸", "required": True, "default": "16:9"},
                ]
            },
            ensure_ascii=False,
        ),
        "image_prompt_template": (
            "城市产业底图，{cities[0]}，{industry}产业氛围，城市地标与产业元素自然融合，"
            "{visual_style}，无文字，无人物特写，适合作为海报背景，比例 {size}"
        ),
        "html_prompt_template": (
            "根据视觉方案和选中底图，生成单文件 HTML 城市产业海报。"
            "城市：{cities}，行业：{industry}，公司：{company_name}，"
            "客户经理：{manager_name}，尺寸：{size}，克制专业的视觉风格。"
        ),
    },
    {
        "id": "product_service_poster",
        "name": "产品服务宣传海报",
        "description": "适合金融产品、服务推广场景",
        "category": "product_service",
        "default_size": "9:16",
        "default_image_count": 4,
        "brief_schema_json": json.dumps(
            {
                "fields": [
                    {"key": "product_name", "label": "产品/服务名称", "required": True},
                    {"key": "key_benefit", "label": "核心卖点", "required": True},
                    {"key": "audience", "label": "目标客群", "required": True},
                    {"key": "cta", "label": "行动号召语", "required": False},
                    {"key": "manager_name", "label": "客户经理姓名", "required": False},
                    {"key": "company_name", "label": "公司名称", "required": True},
                    {"key": "visual_style", "label": "视觉风格", "required": False},
                    {"key": "size", "label": "输出尺寸", "required": True, "default": "9:16"},
                ]
            },
            ensure_ascii=False,
        ),
        "image_prompt_template": (
            "金融产品宣传底图，{visual_style}，现代商务氛围，"
            "无文字，无人物特写，适合作为海报背景，比例 {size}"
        ),
        "html_prompt_template": (
            "根据视觉方案和选中底图，生成单文件 HTML 产品宣传海报。"
            "产品：{product_name}，卖点：{key_benefit}，公司：{company_name}，"
            "客户经理：{manager_name}，尺寸：{size}。"
        ),
    },
]


def _seed_templates(db: Session) -> None:
    """幂等写入内置模板（已存在则跳过）。"""
    for tpl_data in _BUILTIN_TEMPLATES:
        existing = db.get(Template, tpl_data["id"])
        if existing is None:
            db.add(Template(**tpl_data))
    db.commit()


def init_db() -> None:
    """建表 + 创建 workspace 目录 + 写入内置模板。"""
    os.makedirs(settings.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.WORKSPACE_DIR, "projects"), exist_ok=True)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        _seed_templates(db)
