# Agent B 任务规划：Banana 生图 Provider 与批量任务

## 目标
实现 Tuzi 异步生图 Provider、本地文件存储服务，以及批量生成/查询/选择底图的 API 路由，并提供 Provider 单元测试。

## 阶段

### 阶段 1：StorageService ✅
- `backend/app/services/storage_service.py`
- 职责：workspace 目录管理、候选图/选中图保存、远程图片下载、文件读取

### 阶段 2：TuziProvider ✅
- `backend/app/services/image_provider_tuzi.py`
- 职责：multipart 提交任务、轮询状态、兼容 id/task_id/job_id、兼容 video_url/url/image_url

### 阶段 3：routes_generation ✅
- `backend/app/api/routes_generation.py`
- POST /api/campaigns/{campaign_id}/images/batches
- GET  /api/image-batches/{batch_id}
- POST /api/campaigns/{campaign_id}/images/select

### 阶段 4：routes_assets ✅
- `backend/app/api/routes_assets.py`
- GET /api/assets/{asset_id}/file

### 阶段 5：注册路由到 main.py ✅
- 在 main.py 中 include routes_generation 和 routes_assets

### 阶段 6：单元测试 ✅
- `backend/tests/test_image_provider_tuzi.py`
- 覆盖：字段兼容、size 格式、状态解析、失败处理

## 关键设计决策
- batch_id = GenerationTask.id（前端用此 ID 轮询）
- 前端每次 GET /api/image-batches/{batch_id} 触发后端对 Tuzi 的同步轮询（MVP 简单方案）
- 下载图片在 poll 时完成（completed 状态时下载并保存本地）
- reference_asset_ids 从 DB 读取 local_path，读取文件字节后上传
- 不暴露 TUZI_API_KEY 给前端

## 与其他 Agent 的依赖点
- Agent A（已完成）：DB models、schemas、config、errors、state_machine
- Agent C 依赖：StorageService.get_absolute_path（读取选中底图做 base64）
- Agent E 依赖：routes_generation 的响应字段（batch_id、items[].image_asset_id、status、progress、preview_url）
- Agent F 依赖：routes_assets 的 /api/assets/{asset_id}/file
