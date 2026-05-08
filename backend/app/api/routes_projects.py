"""GET /api/projects — 项目列表与详情（落地方案 §5.2）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import Project
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.projects import ProjectListResponse, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ApiResponse[ProjectListResponse])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    items = [ProjectOut.model_validate(p) for p in projects]
    return ApiResponse.success(ProjectListResponse(items=items))


@router.get("/{project_id}", response_model=ApiResponse[ProjectOut])
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project", project_id)
    return ApiResponse.success(ProjectOut.model_validate(project))
