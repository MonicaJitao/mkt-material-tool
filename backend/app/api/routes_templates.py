"""GET /api/templates — 模板列表与详情（落地方案 §9.1）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Template
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.templates import TemplateDetail, TemplateListItem, TemplateListResponse

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=ApiResponse[TemplateListResponse])
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(Template).order_by(Template.name).all()
    items = [TemplateListItem.model_validate(t) for t in templates]
    return ApiResponse.success(TemplateListResponse(items=items))


@router.get("/{template_id}", response_model=ApiResponse[TemplateDetail])
def get_template(template_id: str, db: Session = Depends(get_db)):
    from app.core.errors import NotFoundError

    tpl = db.get(Template, template_id)
    if tpl is None:
        raise NotFoundError("Template", template_id)
    return ApiResponse.success(TemplateDetail.model_validate(tpl))
