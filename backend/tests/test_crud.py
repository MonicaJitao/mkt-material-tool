"""
基础 CRUD 集成测试（落地方案 §12.1）。

使用内存 SQLite，每个测试函数独立数据库，避免状态污染。
覆盖：
- 模板列表与详情
- 项目自动创建
- 活动创建（含 brief / 不含 brief）
- 活动列表与详情
- 404 错误结构
"""

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import _seed_templates, get_db
from app.main import app


def _make_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with TestSession() as db:
        _seed_templates(db)
    return TestSession


@pytest.fixture()
def client():
    TestSession = _make_test_db()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ── /health ───────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── 模板 ──────────────────────────────────────────────────────────────────────

def test_list_templates_returns_three_builtins(client):
    r = client.get("/api/templates")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    items = body["data"]["items"]
    assert len(items) == 3
    ids = {i["id"] for i in items}
    assert ids == {"festival_poster", "city_industry_poster", "product_service_poster"}


def test_get_template_detail(client):
    r = client.get("/api/templates/festival_poster")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] == "festival_poster"
    assert data["default_size"] == "9:16"
    assert data["brief_schema_json"] is not None


def test_get_template_not_found(client):
    r = client.get("/api/templates/nonexistent")
    assert r.status_code == 404
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "NOT_FOUND"


# ── 活动创建 ──────────────────────────────────────────────────────────────────

def test_create_campaign_without_brief(client):
    r = client.post(
        "/api/campaigns",
        json={
            "project_name": "测试项目",
            "campaign_name": "测试活动",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "draft"
    assert body["data"]["campaign_id"].startswith("cmp_")


def test_create_campaign_with_brief_sets_brief_ready(client):
    r = client.post(
        "/api/campaigns",
        json={
            "project_name": "微众银行营销素材",
            "campaign_name": "五一劳动节造城者",
            "template_id": "city_industry_poster",
            "brief": {
                "festival": "五一劳动节",
                "audience": "制造业企业主",
                "theme_hint": "造城者",
                "cities": ["深圳"],
                "manager_name": "杨嘉雯",
                "company_name": "微众银行",
                "visual_style": "明亮摄影融合风格",
                "size": "16:9",
            },
        },
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["status"] == "brief_ready"


def test_create_campaign_invalid_template(client):
    r = client.post(
        "/api/campaigns",
        json={
            "project_name": "测试项目",
            "campaign_name": "测试活动",
            "template_id": "nonexistent_template",
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ── 项目自动创建 ──────────────────────────────────────────────────────────────

def test_same_project_name_reuses_project(client):
    client.post("/api/campaigns", json={"project_name": "共享项目", "campaign_name": "活动A"})
    client.post("/api/campaigns", json={"project_name": "共享项目", "campaign_name": "活动B"})

    r = client.get("/api/projects")
    projects = r.json()["data"]["items"]
    names = [p["name"] for p in projects]
    assert names.count("共享项目") == 1


# ── 活动列表与详情 ────────────────────────────────────────────────────────────

def test_list_campaigns(client):
    client.post("/api/campaigns", json={"project_name": "P1", "campaign_name": "C1"})
    client.post("/api/campaigns", json={"project_name": "P1", "campaign_name": "C2"})

    r = client.get("/api/campaigns")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) >= 2


def test_get_campaign_detail(client):
    create_r = client.post(
        "/api/campaigns",
        json={"project_name": "P", "campaign_name": "详情测试"},
    )
    campaign_id = create_r.json()["data"]["campaign_id"]

    r = client.get(f"/api/campaigns/{campaign_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] == campaign_id
    assert data["name"] == "详情测试"


def test_get_campaign_not_found(client):
    r = client.get("/api/campaigns/nonexistent_id")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# ── 统一响应结构 ──────────────────────────────────────────────────────────────

def test_success_response_shape(client):
    r = client.get("/api/templates")
    body = r.json()
    assert "ok" in body
    assert "data" in body
    assert "error" in body
    assert body["error"] is None


def test_error_response_shape(client):
    r = client.get("/api/campaigns/bad_id")
    body = r.json()
    assert body["ok"] is False
    assert body["data"] is None
    assert "code" in body["error"]
    assert "message" in body["error"]
    assert "details" in body["error"]
