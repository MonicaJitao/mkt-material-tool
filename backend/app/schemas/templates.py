"""Template schemas（落地方案 §5.1 / §9.1）。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TemplateListItem(BaseModel):
    """GET /api/templates 列表项（精简字段，供前端选择模板用）。"""

    id: str
    name: str
    description: str | None = None
    category: str | None = None
    default_size: str
    default_image_count: int

    model_config = {"from_attributes": True}


class TemplateDetail(TemplateListItem):
    """模板详情，含 brief_schema_json 供前端动态渲染表单。"""

    brief_schema_json: str | None = None
    image_prompt_template: str | None = None
    html_prompt_template: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    items: list[TemplateListItem]


class BriefSchemaField(BaseModel):
    """brief_schema_json 内单个字段描述（供前端动态表单使用）。"""

    key: str
    label: str
    required: bool = False
    type: str = "string"
    default: Any = None


class BriefSchema(BaseModel):
    fields: list[BriefSchemaField]
