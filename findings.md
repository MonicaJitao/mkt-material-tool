# Agent B 研究发现

## 后端 API 契约（来自 backend/app/schemas/）

### 统一响应结构
```typescript
{ ok: boolean; data: T | null; error: ErrorDetail | null }
ErrorDetail: { code: string; message: string; details: Record<string, unknown> }
```

### 状态机（落地方案 §4）
```
draft → brief_ready → plan_pending_review → plan_approved
→ image_generating → image_pending_selection → image_selected
→ html_generating → html_ready → editing → archived
失败：failed（附 failed_stage, error_code, error_message）
```

### 关键 Schema 对应
| 前端类型 | 后端 Schema | 文件 |
|---------|------------|------|
| Template | TemplateListItem | schemas/templates.py |
| Project | ProjectOut | schemas/projects.py |
| Campaign | CampaignOut | schemas/campaigns.py |
| ImageBatchItem | ImageBatchItem | schemas/assets.py |
| ImageBatchResponse | ImageBatchResponse | schemas/assets.py |
| HtmlVersionContent | HtmlVersionContent | schemas/html.py |
| HtmlPosterOut | HtmlPosterOut | schemas/html.py |
| GenerationTask | GenerationTaskOut | schemas/generation.py |

## 现有项目结构
- backend/ 已有完整 schemas 和部分 routes
- 无 frontend/ 目录（需从零创建）
- 后端端口：8765（来自落地方案 §14）

## 设计参考
- 落地方案 §10.1 明确要求"营销战役工作台"视觉方向
- 不做通用后台模板感
- 参考：设计软件（Figma/Adobe）的仪式感 + 编辑部工作台
