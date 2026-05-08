"""
本地文件存储服务（落地方案 §6）。

目录结构：
  workspace/projects/<project_slug>/<campaign_slug>/
    assets/candidates/image_v<batch_no>_<slot_no>.<ext>
    assets/selected/selected_image.<ext>
    prompts/
    brief/
    html/
    logs/
"""

import os
from pathlib import Path

import aiofiles
import httpx

from app.core.config import settings


class StorageService:
    def __init__(self, workspace_dir: str | None = None) -> None:
        self._root = Path(workspace_dir or settings.WORKSPACE_DIR).resolve()

    # ── 路径工具 ──────────────────────────────────────────────────────────────

    def campaign_dir(self, project_slug: str, campaign_slug: str) -> Path:
        return self._root / "projects" / project_slug / campaign_slug

    def candidates_dir(self, project_slug: str, campaign_slug: str) -> Path:
        return self.campaign_dir(project_slug, campaign_slug) / "assets" / "candidates"

    def selected_dir(self, project_slug: str, campaign_slug: str) -> Path:
        return self.campaign_dir(project_slug, campaign_slug) / "assets" / "selected"

    def html_dir(self, project_slug: str, campaign_slug: str) -> Path:
        return self.campaign_dir(project_slug, campaign_slug) / "html"

    def prompts_dir(self, project_slug: str, campaign_slug: str) -> Path:
        return self.campaign_dir(project_slug, campaign_slug) / "prompts"

    def absolute_path(self, relative_path: str) -> Path:
        """将数据库中存储的相对路径转为绝对路径。"""
        return self._root / relative_path

    def relative_path(self, absolute: Path) -> str:
        """将绝对路径转为相对于 workspace 根目录的相对路径（用于数据库存储）。"""
        return str(absolute.relative_to(self._root))

    # ── 目录初始化 ────────────────────────────────────────────────────────────

    def ensure_campaign_dirs(self, project_slug: str, campaign_slug: str) -> None:
        for d in [
            self.candidates_dir(project_slug, campaign_slug),
            self.selected_dir(project_slug, campaign_slug),
            self.html_dir(project_slug, campaign_slug),
            self.prompts_dir(project_slug, campaign_slug),
            self.campaign_dir(project_slug, campaign_slug) / "brief",
            self.campaign_dir(project_slug, campaign_slug) / "logs",
        ]:
            d.mkdir(parents=True, exist_ok=True)

    # ── 候选图保存 ────────────────────────────────────────────────────────────

    async def save_candidate_image(
        self,
        project_slug: str,
        campaign_slug: str,
        batch_no: int,
        slot_no: int,
        data: bytes,
        ext: str = "jpg",
    ) -> str:
        """保存候选图，返回相对路径。"""
        dest_dir = self.candidates_dir(project_slug, campaign_slug)
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"image_v{batch_no:03d}_{slot_no:03d}.{ext}"
        dest = dest_dir / filename
        async with aiofiles.open(dest, "wb") as f:
            await f.write(data)
        return self.relative_path(dest)

    # ── 选中图保存 ────────────────────────────────────────────────────────────

    async def save_selected_image(
        self,
        project_slug: str,
        campaign_slug: str,
        data: bytes,
        ext: str = "jpg",
    ) -> str:
        """将选中底图复制到 selected/ 目录，返回相对路径。"""
        dest_dir = self.selected_dir(project_slug, campaign_slug)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"selected_image.{ext}"
        async with aiofiles.open(dest, "wb") as f:
            await f.write(data)
        return self.relative_path(dest)

    # ── HTML 保存 ─────────────────────────────────────────────────────────────

    async def save_html_version(
        self,
        project_slug: str,
        campaign_slug: str,
        version_no: int,
        html_content: str,
    ) -> str:
        """保存 HTML 版本，返回相对路径。"""
        dest_dir = self.html_dir(project_slug, campaign_slug)
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"poster_v{version_no:03d}.html"
        dest = dest_dir / filename
        async with aiofiles.open(dest, "w", encoding="utf-8") as f:
            await f.write(html_content)
        return self.relative_path(dest)

    # ── 文件读取 ──────────────────────────────────────────────────────────────

    async def read_file(self, relative_path: str) -> bytes:
        """读取 workspace 内的文件字节。"""
        abs_path = self.absolute_path(relative_path)
        async with aiofiles.open(abs_path, "rb") as f:
            return await f.read()

    async def read_html(self, relative_path: str) -> str:
        """读取 HTML 文件内容。"""
        abs_path = self.absolute_path(relative_path)
        async with aiofiles.open(abs_path, "r", encoding="utf-8") as f:
            return await f.read()

    def file_exists(self, relative_path: str) -> bool:
        return self.absolute_path(relative_path).exists()

    # ── 远程图片下载 ──────────────────────────────────────────────────────────

    @staticmethod
    async def download_image(url: str, timeout: float = 60.0) -> tuple[bytes, str]:
        """
        下载远程图片，返回 (bytes, ext)。
        ext 从 Content-Type 或 URL 后缀推断。
        """
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        ext = _ext_from_content_type(content_type) or _ext_from_url(url) or "jpg"
        return resp.content, ext


# ── 工具函数 ──────────────────────────────────────────────────────────────────

_CONTENT_TYPE_MAP = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _ext_from_content_type(ct: str) -> str | None:
    ct_base = ct.split(";")[0].strip().lower()
    return _CONTENT_TYPE_MAP.get(ct_base)


def _ext_from_url(url: str) -> str | None:
    path = url.split("?")[0].rstrip("/")
    suffix = os.path.splitext(path)[1].lstrip(".")
    return suffix.lower() if suffix in {"jpg", "jpeg", "png", "webp", "gif"} else None


# ── 单例 ──────────────────────────────────────────────────────────────────────

storage_service = StorageService()
