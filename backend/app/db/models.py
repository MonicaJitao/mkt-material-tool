"""
SQLAlchemy 2.x 声明式数据模型（落地方案 §5）。

所有 ID 使用带前缀的短 UUID 字符串，例如 tpl_xxx、prj_xxx、cmp_xxx。
JSON 字段存为 TEXT，由业务层负责序列化/反序列化。
时间戳统一使用 UTC，由 Python 层写入（避免 SQLite server_default 跨平台差异）。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── Template ──────────────────────────────────────────────────────────────────

class Template(Base):
    """活动模板：保存默认 prompt 组装规则和表单 schema。"""

    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(64))
    default_size: Mapped[str] = mapped_column(String(16), default="9:16")
    default_image_count: Mapped[int] = mapped_column(Integer, default=4)
    brief_schema_json: Mapped[Optional[str]] = mapped_column(Text)
    image_prompt_template: Mapped[Optional[str]] = mapped_column(Text)
    html_prompt_template: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# ── Project ───────────────────────────────────────────────────────────────────

class Project(Base):
    """项目：顶层分类，例如"微众银行节日营销"。"""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    campaigns: Mapped[list["Campaign"]] = relationship("Campaign", back_populates="project")


# ── Campaign ──────────────────────────────────────────────────────────────────

class Campaign(Base):
    """活动：一次具体营销活动，例如"五一劳动节造城者"。"""

    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_campaign_project_slug"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False)
    template_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("templates.id"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)

    # 状态机字段
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    failed_stage: Mapped[Optional[str]] = mapped_column(String(32))
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # JSON 载荷（TEXT 存储，业务层 json.loads/dumps）
    brief_json: Mapped[Optional[str]] = mapped_column(Text)
    structured_plan_json: Mapped[Optional[str]] = mapped_column(Text)
    approved_plan_json: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    project: Mapped["Project"] = relationship("Project", back_populates="campaigns")
    generation_tasks: Mapped[list["GenerationTask"]] = relationship(
        "GenerationTask", back_populates="campaign", cascade="all, delete-orphan"
    )
    image_assets: Mapped[list["ImageAsset"]] = relationship(
        "ImageAsset", back_populates="campaign", cascade="all, delete-orphan"
    )
    html_posters: Mapped[list["HtmlPoster"]] = relationship(
        "HtmlPoster", back_populates="campaign", cascade="all, delete-orphan"
    )


# ── GenerationTask ────────────────────────────────────────────────────────────

class GenerationTask(Base):
    """生成任务：记录一次方案/底图/HTML 生成动作的完整上下文。"""

    __tablename__ = "generation_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), ForeignKey("campaigns.id"), nullable=False)

    # brief_plan / image_batch / html_generation / review
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    failed_stage: Mapped[Optional[str]] = mapped_column(String(32))

    model: Mapped[Optional[str]] = mapped_column(String(128))
    provider: Mapped[Optional[str]] = mapped_column(String(64))

    input_json: Mapped[Optional[str]] = mapped_column(Text)
    prompt_text: Mapped[Optional[str]] = mapped_column(Text)
    output_json: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    raw_error: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="generation_tasks")
    image_assets: Mapped[list["ImageAsset"]] = relationship(
        "ImageAsset", back_populates="generation_task"
    )


# ── ImageAsset ────────────────────────────────────────────────────────────────

class ImageAsset(Base):
    """底图资产：候选图或已选中底图。"""

    __tablename__ = "image_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), ForeignKey("campaigns.id"), nullable=False)
    generation_task_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("generation_tasks.id")
    )

    # candidate / selected
    kind: Mapped[str] = mapped_column(String(16), default="candidate", nullable=False)
    # queued / processing / completed / failed
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0)

    # Tuzi 任务 ID（兼容 id / task_id / job_id）
    provider_task_id: Mapped[Optional[str]] = mapped_column(String(128))

    remote_url: Mapped[Optional[str]] = mapped_column(Text)
    local_path: Mapped[Optional[str]] = mapped_column(Text)   # 相对路径
    prompt_text: Mapped[Optional[str]] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(String(128))
    size: Mapped[Optional[str]] = mapped_column(String(16))
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    selected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="image_assets")
    generation_task: Mapped[Optional["GenerationTask"]] = relationship(
        "GenerationTask", back_populates="image_assets"
    )


# ── HtmlPoster ────────────────────────────────────────────────────────────────

class HtmlPoster(Base):
    """HTML 海报主记录：一个活动可有多个海报（不同底图或重新生成）。"""

    __tablename__ = "html_posters"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), ForeignKey("campaigns.id"), nullable=False)
    selected_image_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("image_assets.id")
    )
    title: Mapped[Optional[str]] = mapped_column(String(256))
    # 指向当前激活版本的 HtmlVersion.id
    current_version_id: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="html_generating", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="html_posters")
    versions: Mapped[list["HtmlVersion"]] = relationship(
        "HtmlVersion",
        back_populates="poster",
        foreign_keys="HtmlVersion.poster_id",
        cascade="all, delete-orphan",
        order_by="HtmlVersion.version_no",
    )


# ── HtmlVersion ───────────────────────────────────────────────────────────────

class HtmlVersion(Base):
    """HTML 版本记录：每次保存/重新生成都产生新版本，不覆盖旧版本。"""

    __tablename__ = "html_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    poster_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("html_posters.id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)

    # model / manual_edit / regenerate
    source: Mapped[str] = mapped_column(String(32), default="model", nullable=False)

    html_path: Mapped[Optional[str]] = mapped_column(Text)   # 相对路径
    prompt_text: Mapped[Optional[str]] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(String(128))
    validation_json: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    poster: Mapped["HtmlPoster"] = relationship(
        "HtmlPoster", back_populates="versions", foreign_keys=[poster_id]
    )
