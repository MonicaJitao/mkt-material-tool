"""
Agent G 集成与验收测试。

覆盖落地方案 §12：
- 创建活动、生成/重生成视觉方案、确认方案
- 创建底图批次、单槽位完成与失败展示、失败后重新生成批次
- 选择底图并落盘到 selected/selected_image.jpg
- 生成 HTML、提取 Claude HTML 结果、预览接口、手动保存新版本
- 文件路径生成与保存版本不覆盖旧版本
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes_html import _extract_html
from app.core.config import settings
from app.db.models import Base
from app.db.session import _seed_templates, get_db
from app.main import app
from app.services.image_provider_tuzi import PollResult, SubmitResult, TuziAPIError
from app.services.storage_service import storage_service


BRIEF = {
    "festival": "五一劳动节",
    "audience": "制造业、科研、软件技术服务业企业主",
    "theme_hint": "造城者",
    "cities": ["深圳"],
    "industry": "先进制造业",
    "manager_name": "杨嘉雯",
    "company_name": "微众银行",
    "visual_style": "明亮摄影融合风格",
    "size": "16:9",
}

PLAN = {
    "campaignTheme": "造城者",
    "audienceInsight": "企业主希望被看见其行业价值",
    "visualStyle": "明亮摄影融合风格",
    "cityLogic": "深圳城市地标 + 产业氛围自然融合",
    "copyTone": "克制、真诚、有行业认同感",
    "layoutRules": {
        "textArea": "底部 1/4",
        "readability": "底部压暗或半透明色块",
    },
}

PROMPTS = {
    "image_prompt": (
        "Bright photographic fusion style, Shenzhen landmark and advanced industry atmosphere, "
        "no text, no words, no letters, no watermark, aspect ratio 16:9, "
        "bottom area reserved for text overlay"
    ),
    "html_prompt": "生成单文件 HTML 海报，底图作为 CSS background-image，文字清晰可读。",
}


@pytest.fixture()
def acceptance_client(tmp_path, monkeypatch):
    workspace_dir = tmp_path / "workspace"
    db_path = tmp_path / "acceptance.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with TestSession() as db:
        _seed_templates(db)

    old_storage_root = storage_service._root
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(workspace_dir))
    storage_service._root = workspace_dir.resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, workspace_dir
    app.dependency_overrides.clear()
    storage_service._root = old_storage_root


def _unwrap(response):
    assert response.status_code < 400, response.text
    body = response.json()
    assert body["ok"] is True
    return body["data"]


def _create_campaign(client: TestClient) -> str:
    data = _unwrap(
        client.post(
            "/api/campaigns",
            json={
                "project_name": "微众银行营销素材",
                "campaign_name": "五一劳动节造城者",
                "template_id": "city_industry_poster",
                "brief": BRIEF,
            },
        )
    )
    assert data["status"] == "brief_ready"
    return data["campaign_id"]


def _generate_and_approve_plan(client: TestClient, campaign_id: str) -> None:
    generated = _unwrap(client.post(f"/api/campaigns/{campaign_id}/plan/generate"))
    assert generated["status"] == "plan_pending_review"
    assert generated["structured_plan"]["campaignTheme"] == "造城者"

    # plan_pending_review 允许重新生成视觉方案，覆盖失败恢复入口之一。
    regenerated = _unwrap(client.post(f"/api/campaigns/{campaign_id}/plan/generate"))
    assert regenerated["status"] == "plan_pending_review"

    approved = _unwrap(
        client.post(
            f"/api/campaigns/{campaign_id}/plan/approve",
            json={"approved_plan": regenerated["structured_plan"]},
        )
    )
    assert approved["status"] == "plan_approved"


def _poster_html(image_path: str, title: str = "造城者") -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      background-image: url('/workspace/{image_path}');
      background-size: cover;
      background-position: center;
      color: #fff;
    }}
    .copy {{ background: rgba(0, 0, 0, .42); padding: 32px; }}
  </style>
</head>
<body>
  <main class="copy">
    <h1>{title}</h1>
    <p>深圳城市地标 + 产业氛围</p>
    <p>微众银行</p>
    <p>客户经理：杨嘉雯</p>
    <p>五一劳动节</p>
  </main>
</body>
</html>"""


def test_claude_html_result_extracts_markdown_fence():
    raw = "```html\n<!doctype html><html><body>造城者</body></html>\n```"
    assert _extract_html(raw) == "<!doctype html><html><body>造城者</body></html>"


def test_end_to_end_acceptance_workflow(acceptance_client):
    client, workspace_dir = acceptance_client

    async def poll_result(task_id: str):
        if task_id == "task_success":
            return PollResult(
                provider_task_id=task_id,
                status="completed",
                progress=100,
                result_url="https://cdn.example.com/selected.jpg",
            )
        return PollResult(
            provider_task_id=task_id,
            status="failed",
            progress=0,
            error_message="上游生图失败",
        )

    with (
        patch(
            "app.services.brief_agent.BriefAgent.generate_plan",
            new_callable=AsyncMock,
            return_value=PLAN,
        ),
        patch(
            "app.services.prompt_agent.PromptAgent.generate_prompts",
            new_callable=AsyncMock,
            return_value=PROMPTS,
        ),
        patch(
            "app.api.routes_generation.tuzi_provider.submit_batch",
            new_callable=AsyncMock,
            return_value=[
                SubmitResult("task_success", status="queued", progress=0),
                SubmitResult("task_failed", status="queued", progress=0),
            ],
        ),
        patch(
            "app.api.routes_generation.tuzi_provider.poll",
            new_callable=AsyncMock,
            side_effect=poll_result,
        ),
        patch(
            "app.api.routes_generation.storage_service.download_image",
            new_callable=AsyncMock,
            return_value=(b"fake image bytes", "jpg"),
        ),
        patch(
            "app.api.routes_html.ClaudeProvider.complete",
            new_callable=AsyncMock,
            return_value=_poster_html(
                "projects/微众银行营销素材/五一劳动节造城者/assets/selected/selected_image.jpg"
            ),
        ),
    ):
        campaign_id = _create_campaign(client)
        _generate_and_approve_plan(client, campaign_id)

        batch = _unwrap(
            client.post(
                f"/api/campaigns/{campaign_id}/images/batches",
                json={
                    "count": 2,
                    "size": "16:9",
                    "model": "gemini-3-pro-image-preview-2k-async",
                    "reference_asset_ids": [],
                },
            )
        )
        assert batch["status"] == "image_generating"
        assert len(batch["items"]) == 2

        batch_status = _unwrap(client.get(f"/api/image-batches/{batch['batch_id']}"))
        assert batch_status["status"] == "image_pending_selection"
        completed = [i for i in batch_status["items"] if i["status"] == "completed"]
        failed = [i for i in batch_status["items"] if i["status"] == "failed"]
        assert len(completed) == 1
        assert len(failed) == 1
        assert completed[0]["preview_url"].startswith("/api/assets/")
        assert failed[0]["error_message"] == "上游生图失败"
        assert "assets/candidates/image_v001_001.jpg" in completed[0]["local_path"].replace("\\", "/")

        selected = _unwrap(
            client.post(
                f"/api/campaigns/{campaign_id}/images/select",
                json={"image_asset_id": completed[0]["image_asset_id"]},
            )
        )
        assert selected["status"] == "image_selected"

        selected_asset = _unwrap(client.get(f"/api/assets/{selected['selected_image_id']}"))
        selected_path = selected_asset["local_path"].replace("\\", "/")
        assert selected_asset["kind"] == "selected"
        assert selected_path.endswith("assets/selected/selected_image.jpg")
        assert not os.path.isabs(selected_asset["local_path"])
        assert (workspace_dir / selected_asset["local_path"]).exists()

        generated_html = _unwrap(
            client.post(
                f"/api/campaigns/{campaign_id}/html/generate",
                json={
                    "selected_image_id": selected["selected_image_id"],
                    "model": "claude-sonnet-4-6",
                },
            )
        )
        assert generated_html["status"] == "html_ready"
        assert generated_html["preview_url"].endswith("/preview")
        assert generated_html["validation"]["ok"] is True

        poster = _unwrap(client.get(f"/api/html/poster/{generated_html['poster_id']}"))
        first_version = poster["versions"][0]
        assert first_version["version_no"] == 1
        assert first_version["html_path"].replace("\\", "/").endswith("html/poster_v001.html")

        first_content = _unwrap(client.get(f"/api/html/{generated_html['version_id']}"))
        assert "造城者" in first_content["html"]
        assert "selected_image.jpg" in first_content["html"]

        edited_html = first_content["html"].replace("造城者", "造城者 · 深圳")
        saved = _unwrap(
            client.post(
                f"/api/html/{generated_html['poster_id']}/versions",
                json={"source": "manual_edit", "html": edited_html},
            )
        )
        assert saved["version_no"] == 2
        assert saved["validation"]["ok"] is True

        updated_poster = _unwrap(client.get(f"/api/html/poster/{generated_html['poster_id']}"))
        assert updated_poster["current_version_id"] == saved["version_id"]
        html_paths = [v["html_path"].replace("\\", "/") for v in updated_poster["versions"]]
        assert html_paths[-2].endswith("html/poster_v001.html")
        assert html_paths[-1].endswith("html/poster_v002.html")
        assert html_paths[-2] != html_paths[-1]

        old_content = _unwrap(client.get(f"/api/html/{generated_html['version_id']}"))
        new_content = _unwrap(client.get(f"/api/html/{saved['version_id']}"))
        assert "造城者 · 深圳" not in old_content["html"]
        assert "造城者 · 深圳" in new_content["html"]

        preview_response = client.get(f"/api/html/{saved['version_id']}/preview")
        assert preview_response.status_code == 200
        assert "text/html" in preview_response.headers["content-type"]


def test_image_batch_can_retry_after_failed_slots(acceptance_client):
    client, _workspace_dir = acceptance_client

    with (
        patch(
            "app.services.brief_agent.BriefAgent.generate_plan",
            new_callable=AsyncMock,
            return_value=PLAN,
        ),
        patch(
            "app.services.prompt_agent.PromptAgent.generate_prompts",
            new_callable=AsyncMock,
            return_value=PROMPTS,
        ),
        patch(
            "app.api.routes_generation.tuzi_provider.submit_batch",
            new_callable=AsyncMock,
            side_effect=[
                [TuziAPIError("上游提交失败", status_code=502)],
                [SubmitResult("task_retry", status="queued", progress=0)],
            ],
        ),
    ):
        campaign_id = _create_campaign(client)
        _generate_and_approve_plan(client, campaign_id)

        first_batch = _unwrap(
            client.post(
                f"/api/campaigns/{campaign_id}/images/batches",
                json={"count": 1, "size": "16:9", "reference_asset_ids": []},
            )
        )
        assert first_batch["items"][0]["status"] == "failed"

        first_status = _unwrap(client.get(f"/api/image-batches/{first_batch['batch_id']}"))
        assert first_status["status"] == "image_pending_selection"

        retry_batch = _unwrap(
            client.post(
                f"/api/campaigns/{campaign_id}/images/batches",
                json={"count": 1, "size": "16:9", "reference_asset_ids": []},
            )
        )
        assert retry_batch["status"] == "image_generating"
        assert retry_batch["items"][0]["provider_task_id"] == "task_retry"
