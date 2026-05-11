/**
 * 前后端共享契约镜像
 * 严格对应 backend/app/schemas/ 中的 Pydantic models
 * 字段名、类型与后端保持一致，不做前端自定义映射
 */

// ── 统一响应结构（schemas/common.py）────────────────────────────

export interface ErrorDetail {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface ApiResponse<T> {
  ok: boolean;
  data: T | null;
  error: ErrorDetail | null;
}

// ── 状态机（落地方案 §4）─────────────────────────────────────────

export type CampaignStatus =
  | 'draft'
  | 'brief_ready'
  | 'plan_pending_review'
  | 'plan_approved'
  | 'image_generating'
  | 'image_pending_selection'
  | 'image_selected'
  | 'html_generating'
  | 'html_ready'
  | 'editing'
  | 'archived'
  | 'failed';

export type TaskType = 'brief_plan' | 'image_batch' | 'html_generation' | 'review';
export type ImageKind = 'candidate' | 'selected';
export type HtmlSource = 'model' | 'manual_edit' | 'regenerate';

// ── 模板（schemas/templates.py）─────────────────────────────────

export interface TemplateListItem {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  default_size: string;
  default_image_count: number;
}

export interface BriefSchemaField {
  key: string;
  label: string;
  required: boolean;
  type: string;
  default: unknown;
}

export interface BriefSchema {
  fields: BriefSchemaField[];
}

export interface TemplateDetail extends TemplateListItem {
  brief_schema_json: string | null;
  image_prompt_template: string | null;
  html_prompt_template: string | null;
  created_at: string;
  updated_at: string;
}

export interface TemplateListResponse {
  items: TemplateListItem[];
}

// ── 项目（schemas/projects.py）──────────────────────────────────

export interface ProjectOut {
  id: string;
  name: string;
  description: string | null;
  slug: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  items: ProjectOut[];
}

// ── 活动（schemas/campaigns.py）─────────────────────────────────

export interface CampaignCreate {
  project_name: string;
  campaign_name: string;
  template_id?: string | null;
  brief?: Record<string, unknown> | null;
}

export interface CampaignCreateResponse {
  campaign_id: string;
  status: CampaignStatus;
}

export interface PlanApproveRequest {
  approved_plan: Record<string, unknown>;
}

export interface PlanApproveResponse {
  campaign_id: string;
  status: CampaignStatus;
}

export interface PlanGenerateRequest {
  model?: string | null;
}

export interface PlanGenerateResponse {
  campaign_id: string;
  task_id: string;
  status: CampaignStatus;
  structured_plan: Record<string, unknown> | null;
}

export interface CampaignOut {
  id: string;
  project_id: string;
  template_id: string | null;
  name: string;
  slug: string;
  status: CampaignStatus;
  failed_stage: string | null;
  error_code: string | null;
  error_message: string | null;
  brief: Record<string, unknown> | null;
  structured_plan: Record<string, unknown> | null;
  approved_plan: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignListResponse {
  items: CampaignOut[];
}

// ── 底图资产（schemas/assets.py）────────────────────────────────

export interface ImageBatchRequest {
  count: number;
  size: string;
  model?: string | null;
  reference_asset_ids: string[];
}

export interface ImageBatchItem {
  image_asset_id: string;
  provider_task_id: string | null;
  status: string;
  progress: number;
  preview_url: string | null;
  local_path: string | null;
  error_message: string | null;
}

export interface ImageBatchResponse {
  batch_id: string;
  status: string;
  items: ImageBatchItem[];
}

export interface ImageBatchStatusResponse {
  batch_id: string;
  status: string;
  items: ImageBatchItem[];
}

export interface ImageSelectRequest {
  image_asset_id: string;
}

export interface ImageSelectResponse {
  campaign_id: string;
  selected_image_id: string;
  status: CampaignStatus;
}

export interface ImageAssetOut {
  id: string;
  campaign_id: string;
  generation_task_id: string | null;
  kind: ImageKind;
  status: string;
  progress: number;
  provider_task_id: string | null;
  remote_url: string | null;
  local_path: string | null;
  prompt_text: string | null;
  model: string | null;
  size: string | null;
  width: number | null;
  height: number | null;
  error_message: string | null;
  selected_at: string | null;
  created_at: string;
}

// ── HTML 海报（schemas/html.py）──────────────────────────────────

export interface HtmlGenerateRequest {
  selected_image_id: string;
  model?: string | null;
}

export interface ValidationResult {
  ok: boolean;
  issues: string[];
}

export interface HtmlGenerateResponse {
  poster_id: string;
  version_id: string;
  status: CampaignStatus;
  preview_url: string;
  validation: ValidationResult;
}

export interface HtmlVersionContent {
  version_id: string;
  poster_id: string;
  version_no: number;
  source: HtmlSource;
  html: string;
  created_at: string;
}

export interface HtmlVersionSaveRequest {
  source: HtmlSource;
  html: string;
}

export interface HtmlVersionSaveResponse {
  poster_id: string;
  version_id: string;
  version_no: number;
  validation: ValidationResult;
}

export interface HtmlVersionOut {
  id: string;
  poster_id: string;
  version_no: number;
  source: HtmlSource;
  html_path: string | null;
  model: string | null;
  validation: Record<string, unknown> | null;
  created_at: string;
}

export interface HtmlPosterOut {
  id: string;
  campaign_id: string;
  selected_image_id: string | null;
  title: string | null;
  current_version_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  versions: HtmlVersionOut[];
}

// ── 生成任务（schemas/generation.py）────────────────────────────

export interface GenerationTaskOut {
  id: string;
  campaign_id: string;
  task_type: TaskType;
  status: string;
  failed_stage: string | null;
  model: string | null;
  provider: string | null;
  input_data: Record<string, unknown> | null;
  prompt_text: string | null;
  output_data: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}
