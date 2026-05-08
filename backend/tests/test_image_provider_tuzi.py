"""
TuziProvider 单元测试（落地方案 §12.1）。

覆盖：
- normalize_size：冒号/x/X/× 格式转换
- _extract_task_id：id / task_id / job_id 兼容
- _extract_result_url：video_url / url / image_url 兼容
- _normalize_status：各种状态字符串归一化
- TuziProvider.submit：成功路径（mock httpx）
- TuziProvider.poll：completed / failed / processing 路径
- TuziProvider.submit_batch：部分失败不影响其他 slot
- StorageService：路径生成、ext 推断
"""

from __future__ import annotations

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.image_provider_tuzi import (
    TuziProvider,
    TuziAPIError,
    TuziConfigError,
    TuziResponseError,
    _extract_result_url,
    _extract_task_id,
    _normalize_status,
    normalize_model,
    normalize_size,
)
from app.services.storage_service import (
    StorageService,
    _ext_from_content_type,
    _ext_from_url,
)


# ── normalize_size ────────────────────────────────────────────────────────────

class TestNormalizeSize:
    def test_colon_format_unchanged(self):
        assert normalize_size("9:16") == "9:16"

    def test_lowercase_x(self):
        assert normalize_size("9x16") == "9:16"

    def test_uppercase_x(self):
        assert normalize_size("16X9") == "16:9"

    def test_multiplication_sign(self):
        assert normalize_size("1×1") == "1:1"

    def test_with_spaces(self):
        assert normalize_size(" 9:16 ") == "9:16"

    def test_square(self):
        assert normalize_size("1:1") == "1:1"


# ── normalize_model ───────────────────────────────────────────────────────────

class TestNormalizeModel:
    def test_async_model_unchanged(self):
        assert normalize_model("gemini-3-pro-image-preview-async") == "gemini-3-pro-image-preview-async"

    def test_base_model_maps_to_async(self):
        assert normalize_model("gemini-3-pro-image-preview") == "gemini-3-pro-image-preview-async"

    def test_2k_alias_maps_to_2k_async(self):
        assert normalize_model("gemini-3-pro-image-preview-2k") == "gemini-3-pro-image-preview-2k-async"

    def test_4k_alias_maps_to_4k_async(self):
        assert normalize_model("gemini-3-pro-image-preview-4k") == "gemini-3-pro-image-preview-4k-async"


# ── _extract_task_id ──────────────────────────────────────────────────────────

class TestExtractTaskId:
    def test_id_field(self):
        assert _extract_task_id({"id": "abc123"}) == "abc123"

    def test_task_id_field(self):
        assert _extract_task_id({"task_id": "task_456"}) == "task_456"

    def test_job_id_field(self):
        assert _extract_task_id({"job_id": "job_789"}) == "job_789"

    def test_id_takes_priority(self):
        assert _extract_task_id({"id": "first", "task_id": "second"}) == "first"

    def test_missing_returns_none(self):
        assert _extract_task_id({"status": "queued"}) is None


# ── _extract_result_url ───────────────────────────────────────────────────────

class TestExtractResultUrl:
    def test_video_url(self):
        assert _extract_result_url({"video_url": "https://cdn.example.com/img.jpg"}) == "https://cdn.example.com/img.jpg"

    def test_url_field(self):
        assert _extract_result_url({"url": "https://cdn.example.com/img.jpg"}) == "https://cdn.example.com/img.jpg"

    def test_image_url_field(self):
        assert _extract_result_url({"image_url": "https://cdn.example.com/img.jpg"}) == "https://cdn.example.com/img.jpg"

    def test_video_url_takes_priority(self):
        assert _extract_result_url({"video_url": "v", "url": "u"}) == "v"

    def test_missing_returns_none(self):
        assert _extract_result_url({"status": "completed"}) is None


# ── _normalize_status ─────────────────────────────────────────────────────────

class TestNormalizeStatus:
    @pytest.mark.parametrize("raw,expected", [
        ("queued", "queued"),
        ("pending", "queued"),
        ("waiting", "queued"),
        ("processing", "processing"),
        ("running", "processing"),
        ("in_progress", "processing"),
        ("completed", "completed"),
        ("succeeded", "completed"),
        ("success", "completed"),
        ("done", "completed"),
        ("failed", "failed"),
        ("error", "failed"),
        ("cancelled", "failed"),
        ("canceled", "failed"),
        ("unknown_status", "unknown_status"),
    ])
    def test_status_normalization(self, raw, expected):
        assert _normalize_status(raw) == expected


# ── TuziProvider.submit ───────────────────────────────────────────────────────

class TestTuziProviderSubmit:
    def _make_provider(self):
        return TuziProvider(api_key="test-key", api_base="https://api.test.com")

    @pytest.mark.asyncio
    async def test_submit_success(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "task_001",
            "status": "queued",
            "progress": 0,
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.submit("test prompt", size="9:16")

        assert result.provider_task_id == "task_001"
        assert result.status == "queued"
        assert result.progress == 0

    @pytest.mark.asyncio
    async def test_submit_uses_task_id_field(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"task_id": "task_002", "status": "queued"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.submit("prompt")

        assert result.provider_task_id == "task_002"

    @pytest.mark.asyncio
    async def test_submit_raises_on_http_error(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Unauthorized"}
        mock_response.text = "Unauthorized"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(TuziAPIError) as exc_info:
                await provider.submit("prompt")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_submit_raises_config_error_without_key(self):
        provider = TuziProvider(api_key="", api_base="https://api.test.com")
        with pytest.raises(TuziConfigError):
            await provider.submit("prompt")

    @pytest.mark.asyncio
    async def test_submit_raises_when_no_task_id(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "queued"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(TuziResponseError):
                await provider.submit("prompt")


# ── TuziProvider.poll ─────────────────────────────────────────────────────────

class TestTuziProviderPoll:
    def _make_provider(self):
        return TuziProvider(api_key="test-key", api_base="https://api.test.com")

    @pytest.mark.asyncio
    async def test_poll_completed(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "task_001",
            "status": "completed",
            "progress": 100,
            "video_url": "https://cdn.example.com/result.jpg",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.poll("task_001")

        assert result.status == "completed"
        assert result.progress == 100
        assert result.result_url == "https://cdn.example.com/result.jpg"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_poll_failed(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "task_001",
            "status": "failed",
            "progress": 0,
            "error": "Content policy violation",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.poll("task_001")

        assert result.status == "failed"
        assert result.result_url is None
        assert "Content policy" in result.error_message

    @pytest.mark.asyncio
    async def test_poll_processing(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "task_001",
            "status": "processing",
            "progress": 50,
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.poll("task_001")

        assert result.status == "processing"
        assert result.progress == 50
        assert result.result_url is None

    @pytest.mark.asyncio
    async def test_poll_uses_image_url_field(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "task_001",
            "status": "completed",
            "progress": 100,
            "image_url": "https://cdn.example.com/img.png",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await provider.poll("task_001")

        assert result.result_url == "https://cdn.example.com/img.png"


# ── TuziProvider.submit_batch ─────────────────────────────────────────────────

class TestTuziProviderSubmitBatch:
    @pytest.mark.asyncio
    async def test_partial_failure_does_not_abort(self):
        """部分 slot 提交失败时，其他 slot 仍然返回结果。"""
        provider = TuziProvider(api_key="test-key", api_base="https://api.test.com")

        call_count = 0

        async def mock_submit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise TuziAPIError("模拟失败", status_code=500)
            from app.services.image_provider_tuzi import SubmitResult
            return SubmitResult(provider_task_id=f"task_{call_count:03d}")

        with patch.object(provider, "submit", side_effect=mock_submit):
            results = await provider.submit_batch("prompt", count=3)

        assert len(results) == 3
        assert not isinstance(results[0], Exception)
        assert isinstance(results[1], TuziAPIError)
        assert not isinstance(results[2], Exception)


# ── StorageService ────────────────────────────────────────────────────────────

class TestStorageService:
    def test_campaign_dir_structure(self, tmp_path):
        svc = StorageService(workspace_dir=str(tmp_path))
        d = svc.campaign_dir("my_project", "my_campaign")
        assert str(d).endswith("my_project/my_campaign") or "my_project" in str(d)

    def test_relative_path_roundtrip(self, tmp_path):
        svc = StorageService(workspace_dir=str(tmp_path))
        abs_path = tmp_path / "projects" / "proj" / "camp" / "assets" / "test.jpg"
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.touch()
        rel = svc.relative_path(abs_path)
        assert svc.absolute_path(rel) == abs_path

    @pytest.mark.asyncio
    async def test_save_candidate_image(self, tmp_path):
        svc = StorageService(workspace_dir=str(tmp_path))
        data = b"fake image bytes"
        rel_path = await svc.save_candidate_image("proj", "camp", 1, 1, data, "jpg")
        assert rel_path.endswith(".jpg")
        assert svc.file_exists(rel_path)
        saved = await svc.read_file(rel_path)
        assert saved == data

    @pytest.mark.asyncio
    async def test_save_selected_image(self, tmp_path):
        svc = StorageService(workspace_dir=str(tmp_path))
        data = b"selected image"
        rel_path = await svc.save_selected_image("proj", "camp", data, "png")
        assert "selected" in rel_path
        assert rel_path.endswith(".png")

    def test_ext_from_content_type(self):
        assert _ext_from_content_type("image/jpeg") == "jpg"
        assert _ext_from_content_type("image/png") == "png"
        assert _ext_from_content_type("image/webp") == "webp"
        assert _ext_from_content_type("image/jpeg; charset=utf-8") == "jpg"
        assert _ext_from_content_type("text/html") is None

    def test_ext_from_url(self):
        assert _ext_from_url("https://cdn.example.com/image.jpg") == "jpg"
        assert _ext_from_url("https://cdn.example.com/image.png?v=1") == "png"
        assert _ext_from_url("https://cdn.example.com/image.webp") == "webp"
        assert _ext_from_url("https://cdn.example.com/image.bmp") is None
        assert _ext_from_url("https://cdn.example.com/noext") is None
